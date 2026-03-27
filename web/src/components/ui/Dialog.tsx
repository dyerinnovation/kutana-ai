import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  className?: string;
}

function Dialog({ open, onClose, children, className }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (open) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      onClick={(e) => {
        // Close on backdrop click
        if (e.target === dialogRef.current) {
          onClose();
        }
      }}
      className={cn(
        "backdrop:bg-gray-950/80 bg-transparent p-0",
        "max-w-lg w-full",
        className
      )}
    >
      <div
        className={cn(
          "rounded-xl border border-gray-700 bg-gray-900 p-6 text-gray-50",
          "shadow-glow-brand"
        )}
      >
        {children}
      </div>
    </dialog>
  );
}

function DialogTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn(
        "mb-4 text-base font-semibold leading-tight tracking-tight text-gray-50",
        className
      )}
      {...props}
    />
  );
}

function DialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("mt-6 flex justify-end gap-3", className)}
      {...props}
    />
  );
}

export { Dialog, DialogTitle, DialogFooter };
