function requiredPublicUrl(name: string, value: string | undefined) {
  if (!value) {
    throw new Error(`${name} is required. Add it to frontend/.env.local.`);
  }
  return value.replace(/\/$/, "");
}

export const API_URL = requiredPublicUrl(
  "NEXT_PUBLIC_API_URL",
  process.env.NEXT_PUBLIC_API_URL,
);

export const WS_URL = requiredPublicUrl(
  "NEXT_PUBLIC_WS_URL",
  process.env.NEXT_PUBLIC_WS_URL,
);
