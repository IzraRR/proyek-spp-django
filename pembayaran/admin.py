# pembayaran/admin.py

import os
import base64
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.db.models import Sum
from .models import Siswa, Tagihan, Pembayaran, BuatTagihanMassal
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

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

@admin.action(description='Download PDF Laporan Tunggakan')
def download_laporan_pdf(modeladmin, request, queryset):
    total_sisa = 0
    for t in queryset:
        total_sisa += t.sisa_tagihan
    gambar_path = os.path.join(settings.BASE_DIR, 'pembayaran/static/pembayaran/images/kop.jpg')    
    encoded_string = ""
    if os.path.exists(gambar_path):
        with open(gambar_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    else:
        print(f"Warning: Image not found at {gambar_path}")

    context = {
        'data_tagihan': queryset.order_by('siswa__kelas', 'siswa__nama_lengkap'),
        'total_sisa': total_sisa,
        'gambar_kop': encoded_string,
    }

    template_path = 'pembayaran/laporan_tunggakan.html'
    template = get_template(template_path)
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="laporan_tunggakan.pdf"'
    pisa_status = pisa.CreatePDF(
       html, 
       dest=response
    )
    if pisa_status.err:
       return HttpResponse('Terjadi kesalahan PDF <pre>' + html + '</pre>')
    return response

@admin.register(Tagihan)
class TagihanAdmin(admin.ModelAdmin):
    list_display = ('judul', 'siswa', 'jumlah_rp', 'jumlah_terbayar', 'sisa_rp', 'status_warna')
    list_filter = ('status', 'bulan', 'siswa__kelas')
    search_fields = ('judul', 'siswa__nama_lengkap')
    list_editable = ('jumlah_terbayar',)
    actions = [download_laporan_pdf]
    
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

@admin.register(Pembayaran)
class PembayaranAdmin(admin.ModelAdmin):
    list_display = ('tagihan', 'jumlah_bayar', 'metode_pembayaran', 'tanggal_bayar', 'id_transaksi_gateway')
    search_fields = ('tagihan__judul', 'id_transaksi_gateway')
    fields = ('tagihan', 'jumlah_bayar', 'metode_pembayaran', 'id_transaksi_gateway')
    readonly_fields = ('id_transaksi_gateway', 'tanggal_bayar')

@admin.register(BuatTagihanMassal)
class BuatTagihanMassalAdmin(admin.ModelAdmin):
    list_display = ('judul_tagihan', 'target_kelas', 'jumlah', 'tanggal_dibuat')
    def response_add(self, request, obj, post_url_continue=None):
        msg = "Proses Berhasil! Tagihan telah dibuatkan untuk semua siswa di kelas tersebut."
        self.message_user(request, msg)
        return super().response_add(request, obj, post_url_continue)