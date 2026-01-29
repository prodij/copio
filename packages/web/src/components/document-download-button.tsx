"use client";

import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3002";

interface DocumentDownloadButtonProps {
  docId: string;
}

export function DocumentDownloadButton({ docId }: DocumentDownloadButtonProps) {
  const handleDownload = async () => {
    try {
      const res = await fetch(`${API_URL}/vendor-documents/${docId}/download-url`);
      if (res.ok) {
        const { downloadUrl } = await res.json();
        window.open(downloadUrl, '_blank');
      }
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  return (
    <Button variant="ghost" size="sm" onClick={handleDownload}>
      <Download className="h-4 w-4" />
    </Button>
  );
}
