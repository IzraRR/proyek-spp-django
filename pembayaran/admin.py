# pembayaran/admin.py (Versi Baru yang Menarik)

from django.contrib import admin
from django.contrib.humanize.templatetags.humanize import intcomma
from .models import Siswa, Tagihan, Pembayaran

# -------------------------------------------------------------------
# Model Inline: Menampilkan data terkait di dalam model lain
# -------------------------------------------------------------------

class TagihanInline(admin.TabularInline):
    """
    Tampilkan daftar tagihan langsung di halaman detail Siswa.
    'TabularInline' membuatnya terlihat seperti tabel.
    """
    model = Tagihan
    fields = ('judul', 'jumlah', 'status', 'bulan', 'tahun') # Tampilkan field ini saja
    extra = 0  # Tidak menampilkan form kosong untuk tagihan baru
    readonly_fields = ('status',) # Status hanya bisa diubah via pembayaran
    can_delete = False
    show_change_link = True # Beri link untuk edit detail tagihan

class PembayaranInline(admin.TabularInline):
    """
    Tampilkan catatan pembayaran di bawah tagihan terkait.
    """
    model = Pembayaran
    extra = 0
    readonly_fields = ('tanggal_bayar', 'jumlah_bayar', 'metode_pembayaran', 'id_transaksi_gateway')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        # Sembunyikan tombol "Add another Pembayaran"
        return False

# -------------------------------------------------------------------
# Model Admin Utama: Kustomisasi tampilan untuk setiap model
# -------------------------------------------------------------------

@admin.register(Siswa)
class SiswaAdmin(admin.ModelAdmin):
    """
    Kustomisasi untuk Halaman Admin Siswa
    """
    list_display = ('nama_lengkap', 'nis', 'kelas', 'user')
    search_fields = ('nama_lengkap', 'nis')
    list_filter = ('kelas',)
    inlines = [TagihanInline] # <- Menampilkan daftar tagihan di bawah detail siswa

    # Mengelompokkan field di halaman edit/tambah siswa
    fieldsets = (
        ('Informasi Login', {
            'fields': ('user',)
        }),
        ('Biodata Siswa', {
            'fields': ('nama_lengkap', 'nis', 'kelas')
        }),
    )

@admin.register(Tagihan)
class TagihanAdmin(admin.ModelAdmin):
    """
    Kustomisasi untuk Halaman Admin Tagihan
    """
    list_display = ('judul', 'siswa', 'get_kelas_siswa', 'jumlah_formatted', 'status', 'tanggal_dibuat')
    search_fields = ('judul', 'siswa__nama_lengkap', 'siswa__nis')
    list_filter = ('status', 'bulan', 'tahun', 'siswa__kelas')
    inlines = [PembayaranInline] # <- Menampilkan catatan pembayaran di bawah detail tagihan
    actions = ['tandai_lunas', 'tandai_belum_lunas'] # <- Menambah menu Aksi

    # Membuat beberapa field hanya bisa dibaca (dikelola sistem)
    readonly_fields = ('status',)

    # Fungsi kustom untuk list_display
    @admin.display(description='Jumlah (Rp)', ordering='jumlah')
    def jumlah_formatted(self, obj):
        # Format angka menjadi "Rp 500.000"
        return f"Rp {intcomma(obj.jumlah)}"

    @admin.display(description='Kelas', ordering='siswa__kelas')
    def get_kelas_siswa(self, obj):
        return obj.siswa.kelas

    # Fungsi Aksi Kustom
    @admin.action(description='Tandai tagihan yang dipilih sebagai LUNAS')
    def tandai_lunas(self, request, queryset):
        queryset.update(status='LUNAS')

    @admin.action(description='Tandai tagihan yang dipilih sebagai BELUM LUNAS')
    def tandai_belum_lunas(self, request, queryset):
        queryset.update(status='BELUM_LUNAS')

@admin.register(Pembayaran)
class PembayaranAdmin(admin.ModelAdmin):
    """ 
    Kustomisasi untuk Halaman Admin Pembayaran (Log Transaksi)
    Model ini seharusnya hanya 'Read-Only' karena dibuat oleh Webhook.
    """
    list_display = ('tagihan', 'tanggal_bayar', 'jumlah_bayar', 'metode_pembayaran', 'id_transaksi_gateway')
    search_fields = ('tagihan__judul', 'id_transaksi_gateway')
    list_filter = ('metode_pembayaran', 'tanggal_bayar')

    # Mencegah Admin menambah, mengubah, atau menghapus log pembayaran
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        # Izinkan melihat (view) tapi tidak mengubah (change)
        return False 
        
    def has_delete_permission(self, request, obj=None):
        return False