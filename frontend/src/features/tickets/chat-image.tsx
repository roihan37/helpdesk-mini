"use client";

import { Alert, Button, Skeleton } from "@/components/ui";
import { Icon } from "@/components/icon";
import { apiRequest, friendlyError, onAccessTokenChanged } from "@/lib/api";
import type { MessageAttachment } from "@/types/api";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";

export function ChatImage({ ticketId, attachment }: {
  ticketId: string;
  attachment: MessageAttachment;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const previewTitleId = useId();

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let objectUrl = "";
    queueMicrotask(() => {
      if (!active) return;
      setLoaded(false);
      setUrl("");
      setError("");
    });
    const unsubscribe = onAccessTokenChanged((token) => {
      if (token === null) {
        active = false;
        controller.abort();
        URL.revokeObjectURL(objectUrl);
        setUrl("");
        dialog.current?.close();
      }
    });
    void apiRequest<Blob>(
      `/tickets/${encodeURIComponent(ticketId)}/attachments/${encodeURIComponent(attachment.id)}`,
      { responseType: "blob", signal: controller.signal }
    ).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch((failure: unknown) => {
      if (active && !controller.signal.aborted) setError(friendlyError(failure, "Image could not be loaded."));
    });
    return () => {
      active = false;
      controller.abort();
      URL.revokeObjectURL(objectUrl);
      unsubscribe();
    };
  }, [ticketId, attachment.id, attempt]);

  return <div className="chat-attachment" data-attachment-pending={!loaded}>
    {error ? <Alert tone="error">{error} <Button variant="quiet" onClick={() => setAttempt((value) => value + 1)}>Retry image</Button></Alert>
      : <>
        {!url ? <div className="chat-image-loading" role="status" style={{ aspectRatio: `${attachment.width} / ${attachment.height}` }}>
          <span className="sr-only">Loading image…</span>
          <Skeleton className="skeleton-image" />
        </div> : null}
        {url ? <Button variant="quiet" className={`chat-image-button${!loaded ? " chat-image-pending" : ""}`} aria-label="Enlarge attached image" disabled={!loaded} onClick={() => dialog.current?.showModal()}>
          <Image src={url} alt="Image attached to this message" width={attachment.width} height={attachment.height}
            unoptimized onLoad={() => setLoaded(true)} onError={() => { setLoaded(false); setError("Image could not be displayed."); }} />
          {!loaded ? <span className="chat-image-overlay" role="status">
            <span className="sr-only">Loading image…</span>
            <Skeleton className="skeleton-image" />
          </span> : null}
        </Button> : null}
      </>}
    <dialog
      ref={dialog}
      className="chat-image-dialog"
      aria-labelledby={previewTitleId}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
          event.currentTarget.close();
        }
      }}
    >
      <div className="chat-image-dialog-heading">
        <div className="chat-image-dialog-info">
          <h2 id={previewTitleId}>Image preview</h2>
          <p>{attachment.width} × {attachment.height} px · {attachment.mime_type.split("/")[1].toUpperCase()} · {Math.ceil(attachment.byte_size / 1024)} KB</p>
        </div>
        <Button
          type="button"
          variant="quiet"
          className="image-preview-close"
          aria-label="Close image preview"
          title="Close image preview"
          autoFocus
          onClick={() => dialog.current?.close()}
        >
          <Icon name="close" />
        </Button>
      </div>
      <div className="chat-image-dialog-stage">
        {url ? <Image src={url} alt="Enlarged image attached to this message" width={attachment.width} height={attachment.height} unoptimized /> : null}
      </div>
      <div className="chat-image-dialog-footer">Click outside or press Esc to close</div>
    </dialog>
  </div>;
}
