import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  DeleteObjectCommand,
} from "@aws-sdk/client-s3"
import { getSignedUrl } from "@aws-sdk/s3-request-presigner"
import { unstable_cache } from "next/cache"

const R2_ACCOUNT_ID = process.env.R2_ACCOUNT_ID!
const R2_ACCESS_KEY_ID = process.env.R2_ACCESS_KEY_ID!
const R2_SECRET_ACCESS_KEY = process.env.R2_SECRET_ACCESS_KEY!
const R2_BUCKET_NAME = process.env.R2_BUCKET_NAME!

export const r2Client = new S3Client({
  region: "auto",
  endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: {
    accessKeyId: R2_ACCESS_KEY_ID,
    secretAccessKey: R2_SECRET_ACCESS_KEY,
  },
})

const PRESIGNED_URL_CACHE_TTL_BUFFER_SECONDS = 300
const cachedDownloadUrlFactories = new Map<
  number,
  (key: string) => Promise<string>
>()
const inFlightDownloadUrlRequests = new Map<string, Promise<string>>()

/**
 * Generate a presigned URL for uploading a file directly to R2.
 */
export async function getUploadPresignedUrl(
  key: string,
  contentType: string,
  expiresIn = 3600
) {
  const command = new PutObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
    ContentType: contentType,
  })

  return getSignedUrl(r2Client, command, { expiresIn })
}

/**
 * Generate a presigned URL for downloading/viewing a file from R2.
 */
export async function getDownloadPresignedUrl(key: string, expiresIn = 3600) {
  const cacheKey = `${expiresIn}:${key}`
  const existingRequest = inFlightDownloadUrlRequests.get(cacheKey)
  if (existingRequest) {
    return existingRequest
  }

  let cachedResolver = cachedDownloadUrlFactories.get(expiresIn)
  if (!cachedResolver) {
    cachedResolver = unstable_cache(
      async (objectKey: string) => {
        const command = new GetObjectCommand({
          Bucket: R2_BUCKET_NAME,
          Key: objectKey,
        })

        return getSignedUrl(r2Client, command, { expiresIn })
      },
      ["r2-download-url", String(expiresIn)],
      {
        revalidate: Math.max(
          60,
          expiresIn - PRESIGNED_URL_CACHE_TTL_BUFFER_SECONDS
        ),
        tags: ["r2-download-url"],
      }
    )
    cachedDownloadUrlFactories.set(expiresIn, cachedResolver)
  }

  const request = cachedResolver(key).finally(() => {
    inFlightDownloadUrlRequests.delete(cacheKey)
  })

  inFlightDownloadUrlRequests.set(cacheKey, request)
  return request
}

/**
 * Delete a file from R2.
 */
export async function deleteFromR2(key: string) {
  const command = new DeleteObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
  })

  return r2Client.send(command)
}

/**
 * Build the public URL for a file (if bucket has public access enabled).
 */
export function getPublicUrl(key: string) {
  const publicUrl = process.env.R2_PUBLIC_URL
  if (!publicUrl) {
    throw new Error("R2_PUBLIC_URL is not configured")
  }
  return `${publicUrl}/${key}`
}

/**
 * Upload a Buffer directly to R2 and return public URL.
 */
export async function uploadFileToR2(
  key: string,
  buffer: Buffer,
  contentType: string
) {
  const command = new PutObjectCommand({
    Bucket: R2_BUCKET_NAME,
    Key: key,
    Body: buffer,
    ContentType: contentType,
  })

  await r2Client.send(command)
  try {
    return getPublicUrl(key)
  } catch {
    return getDownloadPresignedUrl(key, 86400 * 365) // 1 year fallback URL
  }
}

