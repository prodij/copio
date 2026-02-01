import { NextRequest, NextResponse } from "next/server";
import ReactPDF from "@react-pdf/renderer";
import { PODocument } from "./po-document";

const API_URL = process.env.API_URL || "http://localhost:8000/api/v1";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  // Fetch PO data
  const res = await fetch(`${API_URL}/purchase-orders/${id}`, { cache: "no-store" });
  if (!res.ok) {
    return NextResponse.json({ error: "Purchase order not found" }, { status: 404 });
  }
  const po = await res.json();

  // Generate PDF
  const pdfStream = await ReactPDF.renderToStream(<PODocument po={po} />);

  // Convert stream to buffer
  const chunks: Uint8Array[] = [];
  for await (const chunk of pdfStream as AsyncIterable<Uint8Array>) {
    chunks.push(chunk);
  }
  const pdfBuffer = Buffer.concat(chunks);

  // Return PDF response
  return new NextResponse(pdfBuffer, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${po.poNumber}.pdf"`,
    },
  });
}
