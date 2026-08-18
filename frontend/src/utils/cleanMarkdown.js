const LATEX_SYMBOL_REPLACEMENTS = [
  [/\\log/g, "log"],
  [/\\ln/g, "ln"],
  [/\\sqrt/g, "√"],
  [/\\times/g, "×"],
  [/\\cdot/g, "·"],
  [/\\leq/g, "≤"],
  [/\\geq/g, "≥"],
  [/\\neq/g, "≠"],
  [/\\approx/g, "≈"],
  [/\\infty/g, "∞"],
  [/\\sum/g, "Σ"],
  [/\\alpha/g, "α"],
  [/\\beta/g, "β"],
  [/\\theta/g, "θ"],
  [/\\pi/g, "π"],
];

// Gemini is instructed to write plain math ("O(log n)"), but sometimes
// still wraps it in LaTeX delimiters ($...$, \(...\), \[...\], $$...$$)
// out of habit — and this chat has no LaTeX renderer. Strips the
// delimiters and swaps a handful of common LaTeX symbol commands for
// their plain-text/Unicode equivalent, so "$O(\log n)$" reads as
// "O(log n)" instead of showing the raw markup.
export function cleanMathNotation(text) {
  if (!text) {
    return text;
  }

  let cleaned = text
    .replace(/\$\$([^$]+)\$\$/g, (_, inner) => inner)
    .replace(/\\\[(.+?)\\\]/g, (_, inner) => inner)
    .replace(/\\\((.+?)\\\)/g, (_, inner) => inner)
    .replace(/\$([^$\n]+)\$/g, (_, inner) => inner);

  for (const [pattern, replacement] of LATEX_SYMBOL_REPLACEMENTS) {
    cleaned = cleaned.replace(pattern, replacement);
  }

  return cleaned;
}
