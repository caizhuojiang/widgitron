use windows::Win32::Foundation::{HWND, LPARAM, WPARAM};
use windows::Win32::UI::WindowsAndMessaging::{
    EnumWindows, FindWindowW, FindWindowExW, SendMessageTimeoutW, SMTO_NORMAL,
};

fn main() {
    let progman = unsafe { FindWindowW(windows::core::w!("Progman"), None) };
    println!("Progman: {:?}", progman);

    let mut result = 0;
    unsafe {
        SendMessageTimeoutW(
            progman,
            0x052C,
            WPARAM(0),
            LPARAM(0),
            SMTO_NORMAL,
            1000,
            Some(&mut result),
        );
    }

    let mut workerw = HWND(0);
    unsafe {
        EnumWindows(
            Some(enum_window),
            LPARAM(&mut workerw as *mut HWND as isize),
        );
    }
    println!("WorkerW: {:?}", workerw);
}

extern "system" fn enum_window(top_handle: HWND, lparam: LPARAM) -> windows::Win32::Foundation::BOOL {
    let p_workerw = lparam.0 as *mut HWND;
    
    let shell_dll = unsafe {
        FindWindowExW(
            top_handle,
            HWND(0),
            windows::core::w!("SHELLDLL_DefView"),
            None,
        )
    };

    if shell_dll.0 != 0 {
        let next_workerw = unsafe {
            FindWindowExW(
                HWND(0),
                top_handle,
                windows::core::w!("WorkerW"),
                None,
            )
        };
        if next_workerw.0 != 0 {
            unsafe { *p_workerw = next_workerw; }
        }
    }

    true.into()
}
