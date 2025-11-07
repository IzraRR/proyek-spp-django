from django.db import models
from django.contrib.auth.models import User

# Create your models here.
# Model untuk data siswa
class Siswa(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE) # Menghubungkan ke User login
    nis = models.CharField(max_length=20, unique=True) # Nomor Induk Siswa
    nama_lengkap = models.CharField(max_length=100)
    kelas = models.CharField(max_length=10)
    # Tambahkan field lain jika perlu

    class Meta:
        verbose_name = "Siswa"
        verbose_name_plural = "Siswa"

    def __str__(self):
        return self.nama_lengkap

# Model untuk tagihan
class Tagihan(models.Model):
    STATUS_CHOICES = [
        ('BELUM_LUNAS', 'Belum Lunas'),
        ('PENDING', 'Menunggu Pembayaran'),
        ('LUNAS', 'Lunas'),
        ('KADALUARSA', 'Kadaluarsa / Batal'),
    ]

    class Meta:
        verbose_name = "Tagihan"
        verbose_name_plural = "Tagihan"
    
    siswa = models.ForeignKey(Siswa, on_delete=models.CASCADE)
    judul = models.CharField(max_length=200) # Misal: "SPP Bulan Juli 2025"
    jumlah = models.DecimalField(max_digits=10, decimal_places=2)
    bulan = models.CharField(max_length=20)
    tahun = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BELUM_LUNAS')
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.judul} - {self.siswa.nama_lengkap}"

# Model untuk histori pembayaran
class Pembayaran(models.Model):
    tagihan = models.ForeignKey(Tagihan, on_delete=models.CASCADE)
    tanggal_bayar = models.DateTimeField(auto_now_add=True)
    jumlah_bayar = models.DecimalField(max_digits=10, decimal_places=2)
    id_transaksi_gateway = models.CharField(max_length=100) # ID dari Midtrans/Xendit
    metode_pembayaran = models.CharField(max_length=50)

    class Meta:
        verbose_name = "Pembayaran"
        verbose_name_plural = "Pembayaran"

    def __str__(self):
        return f"Pembayaran untuk {self.tagihan.judul}"