"""Native OS memory readings, with no psutil dependency and no guesses for unreadable processes.

RSS sums count shared pages in each process; Windows private commit is reported separately.
An OS peak is per process, not a simultaneous peak of the whole tree: monitor sample maxima for that.
"""
import os
import sys
import time


def _windows_processes():
    import ctypes as c
    from ctypes import wintypes as w
    class Entry(c.Structure):
        _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ProcessID', w.DWORD),
                    ('th32DefaultHeapID', c.c_size_t), ('th32ModuleID', w.DWORD), ('cntThreads', w.DWORD),
                    ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', w.LONG), ('dwFlags', w.DWORD),
                    ('szExeFile', w.WCHAR * 260)]
    k = c.WinDLL('kernel32', use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.Process32FirstW.argtypes = k.Process32NextW.argtypes = [w.HANDLE, c.POINTER(Entry)]
    k.Process32FirstW.restype = k.Process32NextW.restype = w.BOOL
    k.CloseHandle.argtypes = [w.HANDLE]
    handle = k.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
    if handle == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    rows = []
    try:
        entry = Entry()
        entry.dwSize = c.sizeof(entry)
        more = k.Process32FirstW(handle, c.byref(entry))
        while more:
            rows.append(dict(pid=entry.th32ProcessID, ppid=entry.th32ParentProcessID, name=entry.szExeFile))
            more = k.Process32NextW(handle, c.byref(entry))
    finally:
        k.CloseHandle(handle)
    return rows


def processes():
    if sys.platform == 'win32':
        return _windows_processes()
    rows = []
    for name in os.listdir('/proc'):
        if name.isdecimal():
            try:
                with open(f'/proc/{name}/stat') as f:
                    stat = f.read()
                end = stat.rindex(')')
                rows.append(dict(pid=int(name), ppid=int(stat[end + 2:].split()[1]),
                                 name=stat[stat.index('(') + 1:end]))
            except (OSError, ValueError, IndexError):
                pass    # exited while enumerating
    return rows


def _windows_memory(pid):
    import ctypes as c
    from ctypes import wintypes as w
    class Counters(c.Structure):
        _fields_ = [('cb', w.DWORD), ('PageFaultCount', w.DWORD)] + [(n, c.c_size_t) for n in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
            'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage',
            'PrivateUsage')]
    k, p = c.WinDLL('kernel32', use_last_error=True), c.WinDLL('psapi', use_last_error=True)
    k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    p.GetProcessMemoryInfo.argtypes = [w.HANDLE, c.POINTER(Counters), w.DWORD]
    p.GetProcessMemoryInfo.restype = w.BOOL
    handle = k.OpenProcess(0x1000 | 0x0010, False, pid)  # query limited information + VM read
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        counters = Counters()
        counters.cb = c.sizeof(counters)
        if not p.GetProcessMemoryInfo(handle, c.byref(counters), counters.cb):
            raise c.WinError(c.get_last_error())
        return dict(rss_bytes=counters.WorkingSetSize, peak_rss_bytes=counters.PeakWorkingSetSize,
                    private_commit_bytes=counters.PrivateUsage, page_faults=counters.PageFaultCount)
    finally:
        k.CloseHandle(handle)


def process_memory(pid):
    out = dict(pid=pid, rss_bytes=None, peak_rss_bytes=None, private_commit_bytes=None, page_faults=None, error=None)
    try:
        if sys.platform == 'win32':
            out.update(_windows_memory(pid))
        else:
            with open(f'/proc/{pid}/status') as f:
                status = dict(line.split(':', 1) for line in f if ':' in line)
            out['rss_bytes'] = int(status['VmRSS'].split()[0]) * 1024
            out['peak_rss_bytes'] = int(status['VmHWM'].split()[0]) * 1024
    except (OSError, ValueError, KeyError) as exc:
        out['error'] = str(exc)
    return out


def system_memory():
    out = dict(physical_total_bytes=None, physical_available_bytes=None, physical_used_bytes=None,
               commit_used_bytes=None, error=None)
    try:
        if sys.platform == 'win32':
            import ctypes as c
            from ctypes import wintypes as w
            class Status(c.Structure):
                _fields_ = [('dwLength', w.DWORD), ('dwMemoryLoad', w.DWORD)] + [
                    (n, c.c_ulonglong) for n in ('total', 'available', 'total_page', 'available_page',
                                                'total_virtual', 'available_virtual', 'extended')]
            k = c.WinDLL('kernel32', use_last_error=True)
            k.GlobalMemoryStatusEx.argtypes, k.GlobalMemoryStatusEx.restype = [c.POINTER(Status)], w.BOOL
            state = Status()
            state.dwLength = c.sizeof(state)
            if not k.GlobalMemoryStatusEx(c.byref(state)):
                raise c.WinError(c.get_last_error())
            out.update(physical_total_bytes=state.total, physical_available_bytes=state.available,
                       commit_used_bytes=state.total_page - state.available_page)
        else:
            with open('/proc/meminfo') as f:
                info = dict(line.split(':', 1) for line in f)
            out.update(physical_total_bytes=int(info['MemTotal'].split()[0]) * 1024,
                       physical_available_bytes=int(info['MemAvailable'].split()[0]) * 1024)
        out['physical_used_bytes'] = out['physical_total_bytes'] - out['physical_available_bytes']
    except (OSError, ValueError, KeyError) as exc:
        out['error'] = str(exc)
    return out


def _descendants(roots, rows):
    selected = set(roots)
    while True:
        added = {p['pid'] for p in rows if p['ppid'] in selected} - selected
        if not added:
            return selected
        selected.update(added)


def collect(server_pid=None, game_pid=None):
    server_pid = os.getpid() if server_pid is None else server_pid
    rows = processes()
    present = {p['pid'] for p in rows}
    games = ({game_pid} if game_pid in present else set()) if game_pid is not None else {
        p['pid'] for p in rows if p['name'].lower().startswith('beamng.drive')}
    games = _descendants(games, rows)
    servers = _descendants({server_pid} & present, rows) - games
    selected = [dict(p, **{k: v for k, v in process_memory(p['pid']).items() if k != 'pid'},
                     role='game' if p['pid'] in games else 'server')
                for p in rows if p['pid'] in servers | games]
    out = dict(timestamp=time.time(), server_pid=server_pid, system=system_memory(), processes=selected,
               rss_note='Sum of working sets; shared pages may be counted in multiple processes.')
    for role in ('server', 'game'):
        group = [p for p in selected if p['role'] == role]
        out[f'{role}_process_count'] = len(group)
        out[f'{role}_incomplete'] = not group or any(p['error'] for p in group)
        for field in ('rss_bytes', 'private_commit_bytes'):
            values = [p[field] for p in group if p[field] is not None]
            out[f'{role}_{field}'] = sum(values) if values else None
    return out
