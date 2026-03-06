use std::collections::VecDeque;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Mutex, OnceLock};
use std::thread;
use std::time::Duration;
use std::{env, fs::OpenOptions};
use std::fs;

static ENGINE_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn engine_slot() -> &'static Mutex<Option<Child>> {
    ENGINE_CHILD.get_or_init(|| Mutex::new(None))
}

fn resolve_engine_dir(input: &Path) -> Option<PathBuf> {
    if input.join("server.py").exists() {
        return Some(input.to_path_buf());
    }
    let nested = input.join("engine");
    if nested.join("server.py").exists() {
        return Some(nested);
    }
    None
}

#[derive(Clone, Debug)]
struct PythonLaunch {
    program: String,
    pre_args: Vec<String>,
}

fn command_available(program: &str) -> bool {
    let path = PathBuf::from(program);
    if path.is_absolute() {
        return path.exists();
    }
    if program.contains(std::path::MAIN_SEPARATOR) {
        return path.exists();
    }

    let path_var = match env::var_os("PATH") {
        Some(v) => v,
        None => return false,
    };
    #[cfg(windows)]
    let exts: Vec<String> = env::var("PATHEXT")
        .unwrap_or(".EXE;.CMD;.BAT;.COM".to_string())
        .split(';')
        .filter(|s| !s.is_empty())
        .map(|s| s.to_ascii_lowercase())
        .collect();

    for dir in env::split_paths(&path_var) {
        let candidate = dir.join(program);
        if candidate.exists() {
            return true;
        }
        #[cfg(windows)]
        {
            for ext in &exts {
                let with_ext = dir.join(format!("{program}{ext}"));
                if with_ext.exists() {
                    return true;
                }
            }
        }
    }
    false
}

fn resolve_python(engine_dir: &Path) -> Option<PythonLaunch> {
    let candidates = vec![
        PythonLaunch {
            program: engine_dir
                .join(".venv")
                .join("Scripts")
                .join("python.exe")
                .to_string_lossy()
                .to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: engine_dir
                .join(".venv")
                .join("bin")
                .join("python")
                .to_string_lossy()
                .to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: "/opt/homebrew/bin/python3.13".to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: "/usr/local/bin/python3.13".to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: "/usr/bin/python3".to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: "py".to_string(),
            pre_args: vec!["-3".to_string()],
        },
        PythonLaunch {
            program: "python3".to_string(),
            pre_args: vec![],
        },
        PythonLaunch {
            program: "python".to_string(),
            pre_args: vec![],
        },
    ];

    candidates
        .into_iter()
        .find(|candidate| command_available(&candidate.program))
}

fn score_stem_dir(dir: &Path) -> Option<(usize, std::time::SystemTime)> {
    let candidates = [
        "vocals.wav",
        "drums.wav",
        "bass.wav",
        "other.wav",
        "instrumental.wav",
    ];
    let mut count = 0usize;
    let mut newest = std::time::UNIX_EPOCH;
    for name in candidates {
        let p = dir.join(name);
        if p.exists() {
            count += 1;
            if let Ok(meta) = p.metadata() {
                if let Ok(m) = meta.modified() {
                    if m > newest {
                        newest = m;
                    }
                }
            }
        }
    }
    if count > 0 {
        Some((count, newest))
    } else {
        None
    }
}

#[tauri::command]
fn start_engine(engine_dir: String, port: Option<u16>) -> Result<String, String> {
    let port = port.unwrap_or(8732);
    let requested_dir = PathBuf::from(engine_dir);
    if !requested_dir.exists() || !requested_dir.is_dir() {
        return Err("Engine folder does not exist or is not a directory".to_string());
    }
    let dir = resolve_engine_dir(&requested_dir).ok_or_else(|| {
        "Could not find engine/server.py in selected folder. Select the engine folder or repo root."
            .to_string()
    })?;

    let python = resolve_python(&dir).ok_or_else(|| {
        "Python executable not found. Set up engine/.venv or install Python.".to_string()
    })?;

    let slot = engine_slot();
    let mut guard = slot
        .lock()
        .map_err(|_| "Failed to lock engine state".to_string())?;

    if let Some(child) = guard.as_mut() {
        match child.try_wait() {
            Ok(None) => return Ok("Engine already running".to_string()),
            Ok(Some(_)) | Err(_) => {
                *guard = None;
            }
        }
    }

    let log_path = env::temp_dir().join("audiolab-splitter-engine.log");
    let stdout_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Failed to open engine log file: {e}"))?;
    let stderr_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Failed to open engine log file: {e}"))?;

    let mut cmd = Command::new(&python.program);
    cmd.current_dir(dir)
        .args(&python.pre_args)
        .arg("-m")
        .arg("uvicorn")
        .arg("server:app")
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .stdout(Stdio::from(stdout_file))
        .stderr(Stdio::from(stderr_file));

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to start engine process with {:?}: {e}", python))?;

    thread::sleep(Duration::from_millis(500));
    if let Ok(Some(status)) = child.try_wait() {
        return Err(format!(
            "Engine process exited immediately with status {status}. Check log: {}",
            log_path.display()
        ));
    }

    *guard = Some(child);
    Ok(format!(
        "Engine process started from {} using {} (log: {})",
        requested_dir.display(),
        python.program,
        log_path.display()
    ))
}

#[tauri::command]
fn stop_engine() -> Result<String, String> {
    let slot = engine_slot();
    let mut guard = slot
        .lock()
        .map_err(|_| "Failed to lock engine state".to_string())?;

    if let Some(mut child) = guard.take() {
        child
            .kill()
            .map_err(|e| format!("Failed to stop engine process: {e}"))?;
        let _ = child.wait();
        Ok("Engine process stopped".to_string())
    } else {
        Ok("No managed engine process to stop".to_string())
    }
}

#[tauri::command]
fn find_stems_dir(base_dir: String) -> Result<String, String> {
    let base = PathBuf::from(base_dir);
    if !base.exists() || !base.is_dir() {
        return Err("Selected folder does not exist or is not a directory".to_string());
    }

    let mut best_dir: Option<PathBuf> = None;
    let mut best_score: Option<(usize, std::time::SystemTime)> = None;

    let mut q: VecDeque<(PathBuf, usize)> = VecDeque::new();
    q.push_back((base.clone(), 0));
    let max_depth = 5usize;

    while let Some((dir, depth)) = q.pop_front() {
        if let Some(score) = score_stem_dir(&dir) {
            match best_score {
                None => {
                    best_score = Some(score);
                    best_dir = Some(dir.clone());
                }
                Some((best_count, best_time)) => {
                    if score.0 > best_count || (score.0 == best_count && score.1 > best_time) {
                        best_score = Some(score);
                        best_dir = Some(dir.clone());
                    }
                }
            }
        }
        if depth >= max_depth {
            continue;
        }
        let rd = match std::fs::read_dir(&dir) {
            Ok(v) => v,
            Err(_) => continue,
        };
        for e in rd.flatten() {
            let p = e.path();
            if p.is_dir() {
                q.push_back((p, depth + 1));
            }
        }
    }

    if let Some(path) = best_dir {
        Ok(path.to_string_lossy().to_string())
    } else {
        Err("No stems folder found recursively under selected folder".to_string())
    }
}

#[tauri::command]
fn read_binary_file(path: String) -> Result<Vec<u8>, String> {
    let p = PathBuf::from(path);
    if !p.exists() || !p.is_file() {
        return Err("File does not exist".to_string());
    }
    fs::read(&p).map_err(|e| format!("Failed to read file: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            start_engine,
            stop_engine,
            find_stems_dir,
            read_binary_file
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
