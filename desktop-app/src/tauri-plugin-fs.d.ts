declare module "@tauri-apps/plugin-fs" {
  export function readFile(path: string): Promise<Uint8Array>;
  export function writeTextFile(path: string, data: string): Promise<void>;
}
