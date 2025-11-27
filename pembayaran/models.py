# pembayaran/models.py

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete # Import Sinyal
from django.dispatch import receiver # Import penerima sinyal

class Siswa(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nis = models.CharField(max_length=20, unique=True)
    nama_lengkap = models.CharField(max_length=100)
    kelas = models.CharField(max_length=10)
    # (Field tambahan lain jika ada)

    class Meta:
        verbose_name = "Siswa"
        verbose_name_plural = "Siswa"

    def __str__(self):
        return self.nama_lengkap

class Tagihan(models.Model):
    STATUS_CHOICES = [
        ('BELUM_LUNAS', 'Belum Lunas'),
        ('PENDING', 'Menunggu Pembayaran'),
        ('LUNAS', 'Lunas'),
        ('KADALUARSA', 'Kadaluarsa / Batal'),
    ]
    
    siswa = models.ForeignKey(Siswa, on_delete=models.CASCADE)
    judul = models.CharField(max_length=200)
    jumlah = models.DecimalField(max_digits=10, decimal_places=0)
    
    # Field ini dihitung otomatis, jangan diubah manual
    jumlah_terbayar = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    
    bulan = models.CharField(max_length=20)
    tahun = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BELUM_LUNAS')
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tagihan"
        verbose_name_plural = "Tagihan"

    def __str__(self):
        return f"{self.judul} - {self.siswa.nama_lengkap}"

    def save(self, *args, **kwargs):
        # Logika Status Otomatis
        val_jumlah = self.jumlah or 0
        val_terbayar = self.jumlah_terbayar or 0

        if val_terbayar >= val_jumlah:
            self.status = 'LUNAS'
        elif self.status == 'PENDING' or self.status == 'KADALUARSA':
            pass
        else:
            self.status = 'BELUM_LUNAS'
        
        super(Tagihan, self).save(*args, **kwargs)

    @property
    def sisa_tagihan(self):
        val_jumlah = self.jumlah or 0
        val_terbayar = self.jumlah_terbayar or 0
        return val_jumlah - val_terbayar

class Pembayaran(models.Model):
    tagihan = models.ForeignKey(Tagihan, on_delete=models.SET_NULL, null=True, blank=True)
    tanggal_bayar = models.DateTimeField(auto_now_add=True)
    jumlah_bayar = models.DecimalField(max_digits=10, decimal_places=0)
    id_transaksi_gateway = models.CharField(max_length=100, unique=True, blank=True)
    metode_pembayaran = models.CharField(max_length=50, default='MANUAL/CASH')

    class Meta:
        verbose_name = "Pembayaran"
        verbose_name_plural = "Pembayaran"

    def __str__(self):
        return f"Bayar {self.tagihan.judul if self.tagihan else 'Tanpa Tagihan'}"

    def save(self, *args, **kwargs):
        # 1. Generate ID Otomatis jika kosong (Manual Cash)
        if not self.id_transaksi_gateway:
            random_code = uuid.uuid4().hex[:8].upper()
            self.id_transaksi_gateway = f"MANUAL-{random_code}"
        
        super(Pembayaran, self).save(*args, **kwargs)


# =================================================================
# SINYAL OTOMATIS (Mekanisme CCTV)
# =================================================================

@receiver(post_save, sender=Pembayaran)
@receiver(post_delete, sender=Pembayaran)
def update_saldo_tagihan(sender, instance, **kwargs):
    """
    Fungsi ini akan jalan OTOMATIS setiap kali ada Pembayaran
    yang dibuat (save), diedit (save), atau dihapus (delete).
    """
    tagihan = instance.tagihan
    
    if tagihan:
        # 1. Hitung ulang total semua pembayaran yang mengarah ke tagihan ini
        total_masuk = tagihan.pembayaran_set.aggregate(
            total=Sum('jumlah_bayar')
        )['total'] or 0
        
        # 2. Update saldo di Tagihan
        tagihan.jumlah_terbayar = total_masuk
        
        # 3. Simpan Tagihan (ini akan memicu logika LUNAS/BELUM di Tagihan.save())
        tagihan.save()
        print(f"Saldo Tagihan diperbarui: Rp {total_masuk}")