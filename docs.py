"""PDF / Word / metin dosyalarından düz metin çıkarır (macOS'un kendi araçlarıyla, ek paket yok).

- PDF: PDFKit (pyobjc-framework-Quartz ile gelir)
- Word (.docx, .doc), .rtf, .odt, .html, .txt: macOS'teki `textutil` aracı
"""
import subprocess
from pathlib import Path

PDF_EXT = {".pdf"}
TEXTUTIL_EXT = {".docx", ".doc", ".rtf", ".rtfd", ".odt", ".html", ".htm", ".webarchive", ".txt", ".md"}
SUPPORTED_EXT = PDF_EXT | TEXTUTIL_EXT

DOC_NOTE = ("(Bu bir mail DEĞİL: öğrencinin bilgisayarından eklediği bir belge — syllabus, ödev "
            "açıklaması, ders programı vb. Sadece öğrencinin yapması gereken teslim, sınav, quiz, "
            "proje, başvuru tarihlerini al. Belgede yıl yazmıyorsa en yakın mantıklı yılı kullan. "
            "Göreceli tarihleri bugüne göre çevir.)\n\n")


class Unreadable(Exception):
    """Dosyadan metin çıkarılamadı; mesajı kullanıcıya gösterilecek kadar sadedir."""


def _clean(text):
    lines = (" ".join(l.split()) for l in text.splitlines())
    return "\n".join(l for l in lines if l)


def pdf_text_from_bytes(data):
    from Foundation import NSData
    from Quartz import PDFDocument
    doc = PDFDocument.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
    return _pdf_doc_text(doc)


def _pdf_doc_text(doc):
    if doc is None:
        raise Unreadable("PDF açılamadı (bozuk ya da şifreli olabilir).")
    if doc.isLocked():
        raise Unreadable("PDF şifreli, okunamadı.")
    text = _clean(doc.string() or "")
    if len(text) < 20:
        raise Unreadable("PDF'te okunabilir yazı yok (taranmış/fotoğraf PDF olabilir).")
    return text


def file_text(path):
    p = Path(path)
    ext = p.suffix.lower()
    if not p.exists():
        raise Unreadable("Dosya bulunamadı (taşınmış ya da silinmiş olabilir).")
    if ext in PDF_EXT:
        from Foundation import NSURL
        from Quartz import PDFDocument
        return _pdf_doc_text(PDFDocument.alloc().initWithURL_(NSURL.fileURLWithPath_(str(p))))
    if ext in TEXTUTIL_EXT:
        out = subprocess.run(["textutil", "-convert", "txt", "-stdout", str(p)],
                             capture_output=True, text=True, timeout=60)
        text = _clean(out.stdout)
        if out.returncode != 0 or not text:
            raise Unreadable("Dosya okunamadı (bozuk olabilir).")
        return text
    raise Unreadable(f"Bu dosya türü ({ext or 'uzantısız'}) desteklenmiyor. PDF ya da Word dosyası seç.")
