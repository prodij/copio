// The logo (`make brand` writes public/logo.svg from brand/) and the name (from index.html's title).
export function BrandMark({ className }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-semibold ${className ?? ""}`}>
      <img src="/logo.svg" alt="" className="size-6" />
      <span>{document.title}</span>
    </span>
  );
}
