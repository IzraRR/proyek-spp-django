    # pembayaran/admin.py

import os
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib import admin, messages
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Sum
from .models import Siswa, Tagihan, Pembayaran, BuatTagihanMassal
from django.shortcuts import render
from django.utils.html import format_html
from django.urls import reverse

class TagihanInline(admin.TabularInline):
    """
    Tampilkan daftar tagihan langsung di halaman detail Siswa.
    'TabularInline' membuatnya terlihat seperti tabel.
    """
    model = Tagihan
    fields = ('judul', 'jumlah', 'jumlah_terbayar', 'sisa_tagihan_info', 'status')
    readonly_fields = ('sisa_tagihan_info',) # Sisa tagihan dihitung otomatis
    extra = 0

    def sisa_tagihan_info(self, obj):
        return f"Rp {intcomma(obj.sisa_tagihan)}"
    sisa_tagihan_info.short_description = "Sisa Kekurangan"

class PembayaranInline(admin.TabularInline):
    """
    Tampilkan catatan pembayaran di bawah tagihan terkait.
    """
    model = Pembayaran
    extra = 0
    readonly_fields = ('tanggal_bayar', 'jumlah_bayar', 'metode_pembayaran', 'id_transaksi_gateway')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Siswa)
class SiswaAdmin(admin.ModelAdmin):
    list_display = ('nama_lengkap', 'nis', 'kelas', 'total_tagihan_siswa', 'total_tunggakan_siswa')
    search_fields = ('nama_lengkap', 'nis')
    list_filter = ('kelas',)
    inlines = [TagihanInline]

    def total_tagihan_siswa(self, obj):
        total = Tagihan.objects.filter(siswa=obj).aggregate(Sum('jumlah'))['jumlah__sum'] or 0
        return f"Rp {intcomma(total)}"
    total_tagihan_siswa.short_description = "Total Tagihan (Semua)"

    def total_tunggakan_siswa(self, obj):
        tagihan_list = Tagihan.objects.filter(siswa=obj).exclude(status='LUNAS')
        tunggakan = 0
        for t in tagihan_list:
            tunggakan += t.sisa_tagihan
        if tunggakan > 0:
            return f"⚠️ Rp {intcomma(tunggakan)}"
        return "✅ Lunas"
    total_tunggakan_siswa.short_description = "Sisa Tunggakan"

def get_image_base64(filename):
    """Mengubah file gambar menjadi string base64"""
    path = os.path.join(settings.BASE_DIR, 'pembayaran/static/pembayaran/images/', filename)
    if os.path.exists(path):
        with open(path, "rb") as img:
            return base64.b64encode(img.read()).decode('utf-8')
    return None

@admin.action(description='Lihat Laporan Sesuai Status Terpilih')
def view_laporan_tunggakan(modeladmin, request, queryset):
    ada_lunas = queryset.filter(status='LUNAS').exists()
    ada_tunggakan = queryset.exclude(status='LUNAS').exists()
    if ada_lunas and not ada_tunggakan:
        judul = "LAPORAN PEMBAYARAN LUNAS"
    elif ada_tunggakan and not ada_lunas:
        judul = "LAPORAN TUNGGAKAN SISWA"
    else:
        judul = "LAPORAN REKAPITULASI TAGIHAN"
    total_sisa_hitung = 0
    for t in queryset:
        total_sisa_hitung += t.sisa_tagihan
    context = {
        'data_tagihan': queryset.order_by('siswa__kelas', 'siswa__nama_lengkap'),
        'total_sisa': total_sisa_hitung, 
        'judul_laporan': judul,
        'hide_filter': True,
    }
    return render(request, 'pembayaran/laporan_tunggakan_js.html', context)

@admin.register(Tagihan)
class TagihanAdmin(admin.ModelAdmin):
    list_display = ('judul', 'siswa', 'jumlah_rp', 'jumlah_terbayar', 'sisa_rp', 'status_warna', 'tombol_cetak')
    list_filter = ('status', 'tahun', 'bulan', 'siswa__kelas')
    search_fields = ('judul', 'siswa__nama_lengkap')
    list_editable = ('jumlah_terbayar',)
    actions = [view_laporan_tunggakan]
    
    def jumlah_rp(self, obj): return f"Rp {intcomma(obj.jumlah)}"
    
    def sisa_rp(self, obj):
        return f"Rp {intcomma(obj.sisa_tagihan)}"
    sisa_rp.short_description = "Sisa Tagihan"

    def status_warna(self, obj):
        if obj.status == 'LUNAS':
            return "✅ LUNAS"
        elif obj.status == 'PENDING':
            return "⏳ PENDING"
        elif obj.status == 'KADALUARSA':
            return "❌ BATAL"
        else:
            if obj.jumlah_terbayar > 0:
                return "⚠️ BELUM LUNAS (Dicicil)"
            else:
                return "❌ BELUM BAYAR"
    status_warna.short_description = "Status"

    def tombol_cetak(self, obj):
        # Cek apakah tagihan sudah lunas
        pembayaran_terakhir = Pembayaran.objects.filter(tagihan=obj).order_by('id').last()
        
        # 2. Jika ada pembayaran (Entah lunas atau cicilan)
        if pembayaran_terakhir:
            url = reverse('lihat_kwitansi', args=[pembayaran_terakhir.id])
            
            # GAYA 1: Jika sudah LUNAS (Tombol Hijau)
            if  obj.status == 'LUNAS':
                return format_html(
                    '''<a href="{}" target="_blank" 
                       style="background-color: #198754; color: white; padding: 4px 10px; 
                       border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 11px;">
                       🖨️ CETAK LUNAS
                       </a>''', 
                    url
                )
            
            # GAYA 2: Jika masih CICILAN (Tombol Oranye)
            else:
                return format_html(
                    '''<a href="{}" target="_blank" 
                       style="background-color: #fd7e14; color: white; padding: 4px 10px; 
                       border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 11px;">
                       📄 CETAK ANGSURAN
                       </a>''', 
                    url
                )
        
        # 3. Jika belum pernah bayar sama sekali
        return "-"
    
    tombol_cetak.short_description = "Kwitansi" # Judul Header Kolom
    tombol_cetak.allow_tags = True

@admin.register(Pembayaran)
class PembayaranAdmin(admin.ModelAdmin):
    list_display = ('tagihan', 'jumlah_bayar', 'metode_pembayaran', 'tanggal_bayar', 'id_transaksi_gateway')
    search_fields = ('tagihan__judul', 'id_transaksi_gateway')
    fields = ('tagihan', 'jumlah_bayar', 'metode_pembayaran', 'id_transaksi_gateway')
    readonly_fields = ('id_transaksi_gateway', 'tanggal_bayar')

    # === 1. LOGIKA UPDATE SISA TAGIHAN SAAT DISIMPAN ===
    def save_model(self, request, obj, form, change):
        # 1. Simpan pembayaran dulu agar masuk database
        super().save_model(request, obj, form, change)
        
        # 2. Ambil tagihan terkait
        tagihan = obj.tagihan
        
        # 3. Hitung Total Terbayar (Ambil semua history pembayaran)
        # Pastikan field 'jumlah_bayar' sesuai dengan model Pembayaran Anda
        total_bayar = sum(p.jumlah_bayar for p in tagihan.pembayaran_set.all())
        tagihan.jumlah_terbayar = total_bayar
        
        # 4. Cek Status Lunas
        # Kita hitung manual di sini hanya untuk pengecekan if
        # JANGAN lakukan tagihan.sisa_tagihan = ... (Itu penyebab error)
        sisa_saat_ini = tagihan.jumlah - tagihan.jumlah_terbayar

        if sisa_saat_ini <= 0:
            tagihan.lunas = True
            tagihan.status = 'LUNAS'
        else:
            tagihan.lunas = False
            tagihan.status = 'CICILAN'
            
        # 5. Simpan perubahan pada Tagihan
        tagihan.save()

    # === 2. LOGIKA POPUP SETELAH KLIK SAVE ===
    def response_add(self, request, obj, post_url_continue=None):
        # Panggil fungsi bawaan dulu
        response = super().response_add(request, obj, post_url_continue)
        
        # Tambahkan pesan rahasia yang akan dibaca oleh Javascript
        # Format: "CETAK_KWITANSI:ID_PEMBAYARAN"
        messages.success(request, f"CETAK_KWITANSI:{obj.id}")
        
        return response

    # === 3. MASUKKAN JAVASCRIPT KE HALAMAN ADMIN ===
    class Media:
        # Kita butuh SweetAlert2 (Online) dan Script kita sendiri
        js = (
            'https://cdn.jsdelivr.net/npm/sweetalert2@11', # Library Popup
            'admin/js/popup_bayar.js',                     # Script Logika Kita
        )

    # (Opsional) Helper untuk list_display
    def siswa_nama(self, obj):
        return obj.tagihan.siswa.nama_lengkap
    
    def judul_tagihan(self, obj):
        return obj.tagihan.judul

@admin.register(BuatTagihanMassal)
class BuatTagihanMassalAdmin(admin.ModelAdmin):
    list_display = ('judul_tagihan', 'target_kelas', 'jumlah', 'tanggal_dibuat')
    def response_add(self, request, obj, post_url_continue=None):
        msg = "Proses Berhasil! Tagihan telah dibuatkan untuk semua siswa di kelas tersebut."
        self.message_user(request, msg)
        return super().response_add(request, obj, post_url_continue)