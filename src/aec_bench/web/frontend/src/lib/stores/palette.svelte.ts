// ABOUTME: Open/close state for the global search palette overlay.
// ABOUTME: Singleton instance imported by SearchPalette and any caller (NavBar, App).

export class PaletteStore {
  isOpen: boolean = $state(false);
  query: string = $state("");

  open(): void {
    this.isOpen = true;
  }

  close(): void {
    this.isOpen = false;
    this.query = "";
  }

  toggle(): void {
    this.isOpen ? this.close() : this.open();
  }
}

export const paletteStore = new PaletteStore();
