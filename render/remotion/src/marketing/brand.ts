/** Product names for on-screen labels. Set once per render from the root composition's props. */
let product = "Product";
let module = "";

export function setProduct(name?: string, moduleName?: string) {
  if (name) product = name;
  if (moduleName) module = moduleName;
}

export function productName(): string {
  return product;
}

/** Short module name (the first product module) for tight labels; falls back to the product name. */
export function moduleName(): string {
  return module || product;
}
