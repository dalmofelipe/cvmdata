import tempfile

from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _utf8_csv(csv_path: Path):
    """Garante que `read_csv` do DuckDB receba um arquivo em UTF-8.

    Transcodifica com `codecs`/stdlib e entrega UTF-8 puro ao `read_csv`. 
    Se o arquivo já é UTF-8 válido, usa o path original sem reescrever 
    — evita I/O duplo para os CSVs que já vierem nesse formato.

    Uso: `with _utf8_csv(csv_path) as safe_path: ...`
    """
    raw = csv_path.read_bytes()
    try:
        raw.decode("utf-8")
        yield csv_path
        return
    except UnicodeDecodeError:
        pass

    text = raw.decode("cp1252")  # Windows-1252 real da CVM (superset do latin-1)
    fd, tmp_name = tempfile.mkstemp(suffix=".csv", prefix="cvmdata_utf8_")
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(text)
        yield tmp_path
    finally:
        tmp_path.unlink(missing_ok=True)
