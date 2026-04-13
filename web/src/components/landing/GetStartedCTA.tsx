import { Link } from "react-router-dom";

interface Props {
  className?: string;
}

export default function GetStartedCTA({ className = "" }: Props) {
  return (
    <div className={`flex justify-center mt-12 ${className}`}>
      <Link
        to="/register"
        className="inline-flex items-center justify-center px-8 py-3.5 rounded-lg bg-green-600 hover:bg-green-500 text-white font-semibold text-base transition-colors duration-300"
      >
        Get Started Free
      </Link>
    </div>
  );
}
