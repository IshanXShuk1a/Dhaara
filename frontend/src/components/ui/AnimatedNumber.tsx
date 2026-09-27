"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

interface AnimatedNumberProps {
  value: number;
  decimals?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
  flashOnUpdate?: boolean;
}

export function AnimatedNumber({
  value,
  decimals = 0,
  suffix = "",
  prefix = "",
  className,
  flashOnUpdate = true,
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const [isFlashing, setIsFlashing] = useState(false);
  const prevValueRef = useRef(value);

  useEffect(() => {
    if (prevValueRef.current !== value) {
      if (flashOnUpdate) {
        setIsFlashing(true);
        const timer = setTimeout(() => setIsFlashing(false), 400);
        prevValueRef.current = value;
        setDisplayValue(value);
        return () => clearTimeout(timer);
      } else {
        prevValueRef.current = value;
        setDisplayValue(value);
      }
    }
  }, [value, flashOnUpdate]);

  return (
    <span
      className={clsx(
        "tabular-nums transition-colors duration-300 inline-block",
        isFlashing && "animate-value-flash text-accent",
        className
      )}
    >
      {prefix}
      {displayValue.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </span>
  );
}
