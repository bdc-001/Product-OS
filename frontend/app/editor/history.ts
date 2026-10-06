export function createValueStack(limit = 100) {
  const stack: string[] = [];
  let index = -1;

  return {
    reset(value: string) {
      stack.length = 0;
      stack.push(value);
      index = 0;
    },
    push(value: string) {
      if (index >= 0 && stack[index] === value) return;
      stack.splice(index + 1);
      stack.push(value);
      if (stack.length > limit) stack.shift();
      index = stack.length - 1;
    },
    undo(): string | null {
      if (index <= 0) return null;
      index -= 1;
      return stack[index];
    },
    redo(): string | null {
      if (index < 0 || index >= stack.length - 1) return null;
      index += 1;
      return stack[index];
    },
    has() {
      return index >= 0;
    },
  };
}

export function historyAction(event: {
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
  key: string;
  code?: string;
}): "undo" | "redo" | "" {
  if (!(event.metaKey || event.ctrlKey) || event.altKey) return "";
  const key = event.key.toLowerCase();
  const code = event.code || "";
  const isZ = key === "z" || code === "KeyZ";
  const isY = key === "y" || code === "KeyY";
  if (!isZ && !isY) return "";
  if (isY || event.shiftKey) return "redo";
  return "undo";
}
