const fileInput    = document.getElementById('file-input');
const dropZone     = document.getElementById('drop-zone');
const imgPreview   = document.getElementById('img-preview');
const dropHolder   = document.getElementById('drop-placeholder');
const fileInfo     = document.getElementById('file-info');
const btnAnalisis  = document.getElementById('btn-analisis');
const btnText      = document.getElementById('btn-text');
const spinner      = document.getElementById('spinner');
const errorBanner  = document.getElementById('error-banner');
const hasilSection = document.getElementById('hasil-section');

let selectedFile = null;

// ── Drag & Drop ─────────────────────────────────────────────────────────────
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f?.type.startsWith('image/')) handleFile(f);
  else showError('⚠ File harus berupa gambar (JPG, PNG, WEBP).');
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

const cameraInput = document.getElementById('camera-input');
cameraInput.addEventListener('change', () => {
  if (cameraInput.files[0]) handleFile(cameraInput.files[0]);
});

// ── Handle file ──────────────────────────────────────────────────────────────
function handleFile(file) {
  selectedFile = file;
  hideError();
  resetHasil();

  const reader = new FileReader();
  reader.onload = e => {
    imgPreview.src = e.target.result;
    imgPreview.classList.add('show');
    dropHolder.style.display = 'none';
    dropZone.classList.add('has-image');
  };
  reader.readAsDataURL(file);

  document.getElementById('file-info-text').textContent = `✓ ${file.name}  (${(file.size/1024).toFixed(1)} KB)`;
  document.getElementById('file-info-container').style.display = 'flex';

  btnAnalisis.disabled = false;
  btnText.textContent = 'Scan Nutrisi';
}

// ── Analisis ─────────────────────────────────────────────────────────────────
btnAnalisis.addEventListener('click', async () => {
  if (!selectedFile) return;
  setLoading(true);
  hideError();
  resetHasil();

  const form = new FormData();
  form.append('file', selectedFile);

  try {
    const res = await fetch('/api/analisis', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) {
      const msg = data?.detail?.message || data?.detail || data?.error || 'Terjadi kesalahan server.';
      showError('⚠ ' + msg);
      return;
    }
    if (data.error) { showError('⚠ ' + data.error); return; }

    renderHasil(data);
  } catch (err) {
    console.error(err);
    showError('⚠ Tidak dapat terhubung ke server. Pastikan backend berjalan.');
  } finally {
    setLoading(false);
  }
});

// ── Helpers ──────────────────────────────────────────────────────────────────
function setLoading(on) {
  btnAnalisis.disabled = on;
  spinner.style.display = on ? 'block' : 'none';
  btnText.textContent = on ? 'Scanning...' : 'Scan Nutrisi';
}
function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.style.display = 'block';
}
function hideError() {
  errorBanner.style.display = 'none';
}
function resetHasil() {
  hasilSection.style.display = 'none';
  hasilSection.classList.remove('visible');
  const ring = document.getElementById('score-ring');
  if (ring) ring.style.strokeDashoffset = 2 * Math.PI * 32;
}

// ── Fitur Hapus Foto ──
document.getElementById('btn-hapus-foto').addEventListener('click', () => {
  selectedFile = null;
  imgPreview.src = '';
  imgPreview.classList.remove('show');
  document.getElementById('drop-placeholder').style.display = 'flex';
  dropZone.classList.remove('has-image');
  document.getElementById('file-info-container').style.display = 'none';
  
  btnAnalisis.disabled = true;
  btnText.textContent = 'Pilih Gambar Dulu';
  
  document.getElementById('file-input').value = '';
  const camInput = document.getElementById('camera-input');
  if (camInput) camInput.value = '';
  
  resetHasil();
});