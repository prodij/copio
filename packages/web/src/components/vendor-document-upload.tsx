"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Upload, Loader2, AlertCircle, FileText, X } from "lucide-react";

interface VendorDocumentUploadProps {
  vendorId: string;
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

const DOCUMENT_TYPES = [
  { value: "W9", label: "W-9 Tax Form" },
  { value: "COI", label: "Certificate of Insurance" },
  { value: "CONTRACT", label: "Contract/Agreement" },
  { value: "PRICE_LIST", label: "Price List" },
  { value: "PRODUCT_CATALOG", label: "Product Catalog" },
  { value: "SPEC_SHEET", label: "Spec Sheet" },
  { value: "QUALITY_CERT", label: "Quality Certificate" },
  { value: "COMPLIANCE", label: "Compliance Document" },
  { value: "OTHER", label: "Other" },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3002";

export function VendorDocumentUpload({
  vendorId,
  trigger,
  onSuccess,
}: VendorDocumentUploadProps) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [formData, setFormData] = useState({
    type: "OTHER",
    name: "",
    expiresAt: "",
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      // Auto-fill name if empty
      if (!formData.name) {
        setFormData({ ...formData, name: file.name.replace(/\.[^/.]+$/, "") });
      }
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setLoading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Step 1: Get presigned upload URL
      const urlRes = await fetch(`${API_URL}/vendor-documents/upload-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendorId,
          filename: selectedFile.name,
          mimeType: selectedFile.type || "application/octet-stream",
          type: formData.type,
        }),
      });

      if (!urlRes.ok) {
        const data = await urlRes.json();
        throw new Error(data.error || "Failed to get upload URL");
      }

      const { uploadUrl, objectKey, bucket } = await urlRes.json();
      setUploadProgress(20);

      // Step 2: Upload file to MinIO via presigned URL
      const uploadRes = await fetch(uploadUrl, {
        method: "PUT",
        body: selectedFile,
        headers: {
          "Content-Type": selectedFile.type || "application/octet-stream",
        },
      });

      if (!uploadRes.ok) {
        throw new Error("Failed to upload file to storage");
      }
      setUploadProgress(70);

      // Step 3: Create document record in database
      const docRes = await fetch(`${API_URL}/vendor-documents`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vendorId,
          type: formData.type,
          name: formData.name || selectedFile.name,
          objectKey,
          bucket,
          mimeType: selectedFile.type || "application/octet-stream",
          sizeBytes: selectedFile.size,
          expiresAt: formData.expiresAt || undefined,
        }),
      });

      if (!docRes.ok) {
        const data = await docRes.json();
        throw new Error(data.error || "Failed to create document record");
      }
      setUploadProgress(100);

      // Reset and close
      setSelectedFile(null);
      setFormData({ type: "OTHER", name: "", expiresAt: "" });
      setOpen(false);
      router.refresh();
      onSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const defaultTrigger = (
    <Button variant="outline" size="sm">
      <Upload className="h-4 w-4 mr-2" /> Upload Document
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
            <DialogDescription>
              Upload W-9s, certificates, contracts, and other vendor documents.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* File Drop Zone */}
            <div className="space-y-2">
              <Label>File *</Label>
              {!selectedFile ? (
                <div
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Click to select or drag and drop
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    PDF, DOC, XLS, images up to 25MB
                  </p>
                </div>
              ) : (
                <div className="border rounded-lg p-4 flex items-center gap-3">
                  <FileText className="h-8 w-8 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{selectedFile.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(selectedFile.size)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={clearFile}
                    disabled={loading}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileSelect}
                accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.gif"
              />
            </div>

            {/* Document Type */}
            <div className="space-y-2">
              <Label htmlFor="type">Document Type</Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({ ...formData, type: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Display Name */}
            <div className="space-y-2">
              <Label htmlFor="name">Display Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="2024 W-9 Form"
              />
            </div>

            {/* Expiration Date (for certs, contracts) */}
            {["COI", "CONTRACT", "QUALITY_CERT", "COMPLIANCE"].includes(formData.type) && (
              <div className="space-y-2">
                <Label htmlFor="expiresAt">Expiration Date</Label>
                <Input
                  id="expiresAt"
                  type="date"
                  value={formData.expiresAt}
                  onChange={(e) => setFormData({ ...formData, expiresAt: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                  You'll be alerted before documents expire.
                </p>
              </div>
            )}

            {/* Progress Bar */}
            {loading && uploadProgress > 0 && (
              <div className="space-y-1">
                <div className="h-2 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground text-center">
                  {uploadProgress < 70 ? "Uploading..." : "Saving..."}
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive mb-4">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </div>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !selectedFile}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Upload
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
