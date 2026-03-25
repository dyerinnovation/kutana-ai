import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const variantStyles = {
  /** Violet primary — the main call-to-action. */
  default:
    "bg-blue-600 text-white hover:bg-blue-700 focus-visible:ring-blue-500 shadow-sm hover:shadow-glow-brand-sm",
  /** Tonal secondary — less emphasis than primary, more than outline. */
  secondary:
    "bg-gray-800 border border-gray-700 text-gray-100 hover:bg-gray-700 hover:border-gray-600 focus-visible:ring-gray-500",
  /** Transparent with a visible border. */
  outline:
    "border border-gray-700 bg-transparent text-gray-200 hover:bg-gray-800 hover:border-gray-600 focus-visible:ring-gray-500",
  /** No background or border — lowest visual weight. */
  ghost:
    "bg-transparent text-gray-300 hover:bg-gray-800 hover:text-gray-100 focus-visible:ring-gray-500",
  /** Danger/destructive actions. */
  destructive:
    "bg-red-600 text-white hover:bg-red-500 focus-visible:ring-red-500",
};

const sizeStyles = {
  sm: "h-8 px-3 text-xs gap-1.5 rounded-md",
  md: "h-9 px-4 text-sm gap-2 rounded-lg",
  lg: "h-11 px-6 text-sm gap-2 rounded-lg",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium tracking-tight",
          "transition-all duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-950",
          "disabled:pointer-events-none disabled:opacity-40",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        disabled={disabled}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";

export { Button, type ButtonProps };
