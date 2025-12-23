// File: static/admin/js/popup_bayar.js

document.addEventListener('DOMContentLoaded', function() {
    // Cek apakah ada pesan sukses yang mengandung kode unik "CETAK_KWITANSI:"
    const messages = document.querySelectorAll('.messagelist .success');
    
    messages.forEach(function(msg) {
        if (msg.textContent.includes('CETAK_KWITANSI:')) {
            // Ambil ID dari pesan teks (Format: "CETAK_KWITANSI:15")
            const text = msg.textContent;
            const parts = text.split(':');
            const pembayaranId = parts[parts.length - 1].trim(); // Ambil angka terakhir

            // Tampilkan SweetAlert
            Swal.fire({
                title: 'Pembayaran Berhasil!',
                text: 'Data telah disimpan. Cetak kwitansi sekarang?',
                icon: 'success',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: '🖨️ Ya, Cetak Kwitansi',
                cancelButtonText: 'Tutup'
            }).then((result) => {
                if (result.isConfirmed) {
                    // Redirect ke halaman cetak (Sesuaikan URL jika perlu)
                    window.open('/kwitansi/' + pembayaranId + '/', '_blank');
                }
            });

            // Sembunyikan pesan teks asli agar tidak jelek
            msg.style.display = 'none';
        }
    });
});