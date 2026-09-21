"""One shared data-only stream, leased by open browser panels."""
import json
import subprocess
import threading
import time


class Stream:
    def __init__(self, root, symbol="QQQ"):
        self.symbol=symbol
        self.root=root
        self.output=root/'data/kronos_lab/stream'
        if symbol!='QQQ':self.output=self.output/symbol
        self.process=None
        self.lock=threading.Lock()

    def poll(self):
        with self.lock:
            self.output.mkdir(parents=True,exist_ok=True)
            (self.output/'lease').touch()
            if self.process is None or self.process.poll() is not None:
                (self.output/'latest.json').write_text('{}')
                self.process=subprocess.Popen(
                    [r'C:\Users\ruley\WebullTradingScanner\.venv\Scripts\python.exe',str(self.root/'scripts/webull_stream_worker.py'),self.symbol],
                    cwd=self.root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try: state=json.loads((self.output/'latest.json').read_text())
            except (OSError,ValueError):state={}
            state['stale']=time.time()-state.get('received_at',0)>10
            return state
