"use client";

import { Alert, Button } from "@/components/ui";
import { apiRequest, friendlyError, onAccessTokenChanged } from "@/lib/api";
import type { MessageAttachment } from "@/types/api";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

export function ChatImage({ ticketId, attachment }: {
  ticketId: string;
  attachment: MessageAttachment;
}) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let objectUrl = "";
    setLoaded(false);
    setUrl("");
    setError("");
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
      : !url ? <span role="status">Loading image…</span>
        : <Button variant="quiet" className="chat-image-button" aria-label="Enlarge attached image" onClick={() => dialog.current?.showModal()}>
          <Image src={url} alt="Image attached to this message" width={attachment.width} height={attachment.height}
            unoptimized onLoad={() => setLoaded(true)} onError={() => { setLoaded(false); setError("Image could not be displayed."); }} />
        </Button>}
    <dialog ref={dialog} className="chat-image-dialog" aria-label="Attached image preview">
      <Button variant="secondary" autoFocus onClick={() => dialog.current?.close()}>Close preview</Button>
      {url ? <Image src={url} alt="Enlarged image attached to this message" width={attachment.width} height={attachment.height} unoptimized /> : null}
    </dialog>
  </div>;
}
