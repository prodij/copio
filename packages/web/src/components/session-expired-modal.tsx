"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { LogIn } from "lucide-react";

interface SessionExpiredModalProps {
  open: boolean;
  onLogin: () => void;
}

export function SessionExpiredModal({ open, onLogin }: SessionExpiredModalProps) {
  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-md" onPointerDownOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <LogIn className="h-5 w-5" />
            Session Expired
          </DialogTitle>
          <DialogDescription>
            Your session has expired due to inactivity. Please log in again to continue.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <Button onClick={onLogin} className="w-full">
            <LogIn className="mr-2 h-4 w-4" />
            Log In
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
