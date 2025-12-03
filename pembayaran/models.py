# pembayaran/models.py

import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver 

class Siswa(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nis = models.CharField(max_length=20, unique=True)
    nama_lengkap = models.CharField(max_length=100)
    kelas = models.CharField(max_length=10)

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
        if not self.id_transaksi_gateway:
            random_code = uuid.uuid4().hex[:8].upper()
            self.id_transaksi_gateway = f"MANUAL-{random_code}"
        
        super(Pembayaran, self).save(*args, **kwargs)

class BuatTagihanMassal(models.Model):
    KELAS_CHOICES = [
        ('7', '7'),
        ('8', '8'),
        ('9', '9'),
        ('SEMUA', 'Semua Kelas'),
    ]

    target_kelas = models.CharField(max_length=10, choices=KELAS_CHOICES)
    judul_tagihan = models.CharField(max_length=200, help_text="Contoh: SPP Bulan Agustus 2025")
    jumlah = models.DecimalField(max_digits=10, decimal_places=0)
    bulan = models.CharField(max_length=20)
    tahun = models.IntegerField()
    
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Buat Tagihan Massal"
        verbose_name_plural = "Buat Tagihan Massal"

    def __str__(self):
        return f"Batch: {self.judul_tagihan} ({self.target_kelas})"
    def save(self, *args, **kwargs):
        super(BuatTagihanMassal, self).save(*args, **kwargs)
        if self.target_kelas == 'SEMUA':
            siswa_list = Siswa.objects.all()
        else:
            siswa_list = Siswa.objects.filter(kelas=self.target_kelas)
        jumlah_dibuat = 0
        for s in siswa_list:
            cek_ada = Tagihan.objects.filter(
                siswa=s, 
                judul=self.judul_tagihan, 
                bulan=self.bulan, 
                tahun=self.tahun
            ).exists()
            
            if not cek_ada:
                Tagihan.objects.create(
                    siswa=s,
                    judul=self.judul_tagihan,
                    jumlah=self.jumlah,
                    bulan=self.bulan,
                    tahun=self.tahun,
                    status='BELUM_LUNAS'
                )
                jumlah_dibuat += 1
        
        print(f"SUKSES: {jumlah_dibuat} tagihan berhasil dibuat untuk kelas {self.target_kelas}")

@receiver(post_save, sender=Pembayaran)
@receiver(post_delete, sender=Pembayaran)
def update_saldo_tagihan(sender, instance, **kwargs):

    tagihan = instance.tagihan
    
    if tagihan:
        total_masuk = tagihan.pembayaran_set.aggregate(
            total=Sum('jumlah_bayar')
        )['total'] or 0
        tagihan.jumlah_terbayar = total_masuk
        tagihan.save()
        print(f"Saldo Tagihan diperbarui: Rp {total_masuk}")