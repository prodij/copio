"use client";

import { cn } from "@/lib/utils";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

export function Logo({ size = "md", showText = true, className }: LogoProps) {
  const sizes = {
    sm: { icon: "h-8 w-8", cube: "h-2 w-2", text: "text-lg", gap: "gap-2" },
    md: { icon: "h-10 w-10", cube: "h-2.5 w-2.5", text: "text-2xl", gap: "gap-2" },
    lg: { icon: "h-14 w-14", cube: "h-3 w-3", text: "text-3xl", gap: "gap-3" },
  };

  const s = sizes[size];

  return (
    <div className={cn("flex items-center", s.gap, className)}>
      {/* Animated stacked cubes icon */}
      <div className={cn("relative", s.icon)}>
        {/* Glow effect */}
        <div className="absolute inset-0 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-xl blur-lg opacity-40 animate-pulse" />
        
        {/* Icon container */}
        <div className="relative h-full w-full bg-gradient-to-br from-violet-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
          {/* 3D stacked cubes */}
          <div className="grid grid-cols-2 gap-0.5 transform rotate-3">
            <div className={cn(s.cube, "bg-white/90 rounded-sm shadow-sm")} />
            <div className={cn(s.cube, "bg-white/70 rounded-sm shadow-sm")} />
            <div className={cn(s.cube, "bg-white/70 rounded-sm shadow-sm")} />
            <div className={cn(s.cube, "bg-white/50 rounded-sm shadow-sm")} />
          </div>
        </div>
      </div>

      {showText && (
        <span className={cn(
          s.text,
          "font-bold tracking-tight",
          "bg-gradient-to-r from-gray-900 via-gray-800 to-gray-900 dark:from-white dark:via-gray-200 dark:to-white",
          "bg-clip-text text-transparent"
        )}>
          Copio
        </span>
      )}
    </div>
  );
}
