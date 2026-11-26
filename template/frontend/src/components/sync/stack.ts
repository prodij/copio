// Below the `sm` breakpoint (640px) a table row stacks into a two-column card instead of
// scrolling sideways, so every column and action stays on screen. The header row is kept for
// screen readers; a cell that needs its column name on a phone shows it from `data-label`.
export const stack = {
  table: "max-sm:block",
  head: "max-sm:sr-only",
  body: "max-sm:block",
  row: "max-sm:grid max-sm:grid-cols-2 max-sm:gap-x-4 max-sm:gap-y-2 max-sm:py-3",
  cell: "max-sm:block max-sm:py-0 max-sm:pr-0",
  wide: "max-sm:col-span-2",
  labelled:
    "max-sm:before:mb-0.5 max-sm:before:block max-sm:before:text-xs max-sm:before:text-muted-foreground max-sm:before:content-[attr(data-label)]",
};
