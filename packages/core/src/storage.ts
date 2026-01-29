import { Client } from 'minio';

// MinIO client singleton
let minioClient: Client | null = null;

export function getMinioClient(): Client {
  if (!minioClient) {
    minioClient = new Client({
      endPoint: process.env.MINIO_ENDPOINT || 'localhost',
      port: parseInt(process.env.MINIO_PORT || '9000'),
      useSSL: process.env.MINIO_USE_SSL === 'true',
      accessKey: process.env.MINIO_ACCESS_KEY || 'minioadmin',
      secretKey: process.env.MINIO_SECRET_KEY || 'minioadmin',
    });
  }
  return minioClient;
}

// Bucket names
export const BUCKETS = {
  VENDOR_DOCUMENTS: 'vendor-documents',
  PRODUCT_IMAGES: 'product-images',
} as const;

// Initialize buckets (call on startup)
export async function initializeBuckets(): Promise<void> {
  const client = getMinioClient();
  
  for (const bucket of Object.values(BUCKETS)) {
    const exists = await client.bucketExists(bucket);
    if (!exists) {
      await client.makeBucket(bucket);
      console.log(`Created bucket: ${bucket}`);
    }
  }
}

// Generate a presigned URL for upload
export async function getPresignedUploadUrl(
  bucket: string,
  objectKey: string,
  expirySeconds = 3600
): Promise<string> {
  const client = getMinioClient();
  return client.presignedPutObject(bucket, objectKey, expirySeconds);
}

// Generate a presigned URL for download
export async function getPresignedDownloadUrl(
  bucket: string,
  objectKey: string,
  expirySeconds = 3600
): Promise<string> {
  const client = getMinioClient();
  return client.presignedGetObject(bucket, objectKey, expirySeconds);
}

// Upload a buffer directly
export async function uploadBuffer(
  bucket: string,
  objectKey: string,
  buffer: Buffer,
  mimeType: string
): Promise<void> {
  const client = getMinioClient();
  await client.putObject(bucket, objectKey, buffer, buffer.length, {
    'Content-Type': mimeType,
  });
}

// Delete an object
export async function deleteObject(
  bucket: string,
  objectKey: string
): Promise<void> {
  const client = getMinioClient();
  await client.removeObject(bucket, objectKey);
}

// Get object metadata
export async function getObjectInfo(
  bucket: string,
  objectKey: string
) {
  const client = getMinioClient();
  return client.statObject(bucket, objectKey);
}
