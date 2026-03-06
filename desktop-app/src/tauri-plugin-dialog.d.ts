declare module "@tauri-apps/plugin-dialog" {
  export interface DialogFilter {
    name: string;
    extensions: string[];
  }

  export interface OpenDialogOptions {
    directory?: boolean;
    multiple?: boolean;
    title?: string;
    filters?: DialogFilter[];
  }

  export function open(options?: OpenDialogOptions): Promise<string | string[] | null>;
}
