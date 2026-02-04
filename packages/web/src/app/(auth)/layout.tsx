import { ReactNode } from "react";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex flex-col justify-between p-10 bg-gradient-to-br from-violet-600 via-indigo-600 to-violet-700 text-white relative overflow-hidden">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} />
        </div>
        
        {/* Logo */}
        <div className="relative z-10">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 bg-white/20 backdrop-blur rounded-xl flex items-center justify-center">
              <div className="grid grid-cols-2 gap-0.5">
                <div className="h-2.5 w-2.5 bg-white rounded-sm" />
                <div className="h-2.5 w-2.5 bg-white/70 rounded-sm" />
                <div className="h-2.5 w-2.5 bg-white/70 rounded-sm" />
                <div className="h-2.5 w-2.5 bg-white/50 rounded-sm" />
              </div>
            </div>
            <span className="text-2xl font-bold tracking-tight">Copio</span>
          </div>
        </div>

        {/* Value prop */}
        <div className="relative z-10 space-y-6">
          <blockquote className="space-y-4">
            <p className="text-3xl font-medium leading-tight">
              &ldquo;Multi-marketplace inventory management that actually works.&rdquo;
            </p>
            <footer className="text-white/70">
              <p className="font-medium text-white">Unified Inventory</p>
              <p>Sync across Amazon, eBay, Shopify & more</p>
            </footer>
          </blockquote>
        </div>

        {/* Footer */}
        <div className="relative z-10 text-sm text-white/50">
          © {new Date().getFullYear()} Copio. All rights reserved.
        </div>
      </div>

      {/* Right Panel - Form */}
      <div className="flex items-center justify-center p-6 sm:p-10 bg-background">
        {children}
      </div>
    </div>
  );
}
