package com.touchstation.ps3

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.BitmapFactory
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.InputDevice
import android.view.View
import android.util.Base64
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.util.Locale

class MainActivity : Activity() {
    private lateinit var root: LinearLayout
    private lateinit var content: LinearLayout
    private val prefs by lazy { getSharedPreferences("touchstation", Context.MODE_PRIVATE) }
    private var game: Uri? = null
    private var firmware: Uri? = null

    private val logoBitmap by lazy {
        val encoded = resources.openRawResource(R.raw.touchstation_logo).bufferedReader().use { it.readText() }
        val bytes = Base64.decode(encoded, Base64.DEFAULT)
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
    }

    private val blue = Color.rgb(35, 112, 245)
    private val pageBackground = Color.rgb(7, 10, 17)
    private val panelBackground = Color.rgb(20, 28, 42)
    private val muted = Color.rgb(166, 178, 198)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        game = prefs.getString("game_uri", null)?.let(Uri::parse)
        firmware = prefs.getString("firmware_uri", null)?.let(Uri::parse)
        home()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun page(title: String, subtitle: String) {
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(18), dp(18), dp(12))
            setBackgroundColor(pageBackground)
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        header.addView(ImageView(this).apply {
            setImageBitmap(logoBitmap)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "TouchStation PS3 logo"
        }, LinearLayout.LayoutParams(dp(92), dp(92)))

        val heading = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), 0, 0, 0)
        }
        heading.addView(TextView(this).apply {
            text = title
            textSize = 23f
            setTextColor(Color.WHITE)
            typeface = Typeface.DEFAULT_BOLD
        })
        heading.addView(TextView(this).apply {
            text = subtitle
            textSize = 12f
            setTextColor(muted)
            setPadding(0, dp(4), 0, 0)
        })
        header.addView(heading, LinearLayout.LayoutParams(0, -2, 1f))
        root.addView(header)

        content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(18), 0, dp(12))
        }
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(content)
        }
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

        val nav = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        listOf("Home", "Library", "Firmware", "Settings").forEach { label ->
            nav.addView(Button(this).apply {
                text = label
                textSize = 10f
                isAllCaps = false
                setTextColor(if (label == currentPage) blue else Color.WHITE)
                backgroundTintList = ColorStateList.valueOf(panelBackground)
                setOnClickListener {
                    when (label) {
                        "Home" -> home()
                        "Library" -> library()
                        "Firmware" -> firmwarePage()
                        else -> settings()
                    }
                }
            }, LinearLayout.LayoutParams(0, dp(46), 1f).apply {
                marginEnd = dp(4)
            })
        }
        root.addView(nav)
        setContentView(root)
    }

    private var currentPage = "Home"

    private fun card(title: String, body: String, accent: Boolean = false) {
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = android.graphics.drawable.GradientDrawable().apply {
                setColor(panelBackground)
                cornerRadius = dp(14).toFloat()
                if (accent) setStroke(dp(1), blue)
            }
        }
        panel.addView(TextView(this).apply {
            text = title
            textSize = 15f
            typeface = Typeface.DEFAULT_BOLD
            setTextColor(Color.WHITE)
        })
        panel.addView(TextView(this).apply {
            text = body
            textSize = 13f
            setTextColor(muted)
            setPadding(0, dp(7), 0, 0)
        })
        content.addView(panel, LinearLayout.LayoutParams(-1, -2).apply {
            bottomMargin = dp(10)
        })
    }

    private fun actionButton(label: String, action: () -> Unit, enabled: Boolean = true) {
        content.addView(Button(this).apply {
            text = label
            isAllCaps = false
            textSize = 14f
            isEnabled = enabled
            setTextColor(Color.WHITE)
            backgroundTintList = ColorStateList.valueOf(if (enabled) blue else Color.DKGRAY)
            setOnClickListener { action() }
        }, LinearLayout.LayoutParams(-1, dp(50)).apply {
            bottomMargin = dp(9)
        })
    }

    private fun home() {
        currentPage = "Home"
        page("TouchStation PS3", "version 2.0.0 · android")
        card("GAME", game?.let { "${displayName(it)}\n${fileSummary(it)}" } ?: "no game imported yet")
        card("SYSTEM FIRMWARE", firmware?.let {
            if (isValidPup(it)) "${displayName(it)}\nPUP header verified" else "${displayName(it)}\nfirmware file could not be verified"
        } ?: "PS3UPDATE.PUP has not been imported")
        val ready = game != null && firmware?.let(::isValidPup) == true
        card("SYSTEM STATUS", if (ready) {
            "game and firmware files are selected. the emulator engine is not integrated in this build, so game boot is unavailable."
        } else {
            "import one supported game file and your PS3UPDATE.PUP. the emulator engine is not integrated in this build yet."
        }, accent = true)
        actionButton("Import game") { library() }
        actionButton("Import PS3 firmware") { firmwarePage() }
        actionButton("Boot game", { Toast.makeText(this, "game boot is unavailable: no PS3 emulation core is linked.", Toast.LENGTH_LONG).show() }, enabled = false)
    }

    private fun library() {
        currentPage = "Library"
        page("Game library", "your imported PS3 game")
        card("SELECTED GAME", game?.let {
            "${displayName(it)}\n${fileSummary(it)}\nformat: ${extension(it).uppercase(Locale.US)}"
        } ?: "no game selected")
        actionButton("Choose game file") { pick(100) }
        actionButton("Remove imported game", {
            game = null
            prefs.edit().remove("game_uri").apply()
            library()
        }, enabled = game != null)
        card("SUPPORTED FILE TYPES", "ISO disc images, PKG packages, SELF executables, and ELF executables. choose one game file; no extra metadata or support files are requested.")
        card("BOOT STATUS", "file import and identification only. PPU/SPU execution, RSX rendering, and game boot require an emulator core that is not currently included.")
    }

    private fun firmwarePage() {
        currentPage = "Firmware"
        page("System firmware", "import the official PS3 update package")
        val valid = firmware?.let(::isValidPup) == true
        card("PS3UPDATE.PUP", firmware?.let {
            "${displayName(it)}\n${fileSummary(it)}\n${if (valid) "SCE PUP header verified" else "file header not recognised"}"
        } ?: "no firmware imported")
        actionButton("Choose firmware file") { pick(101) }
        actionButton("Remove firmware", {
            firmware = null
            prefs.edit().remove("firmware_uri").apply()
            firmwarePage()
        }, enabled = firmware != null)
        card("FIRMWARE HANDLING", "this build checks the PUP signature and keeps a persistent read-only document reference. installation into an emulated PS3 system is not implemented without the emulator core.")
        card("PRIVACY", "firmware and game files stay in the storage location you selected. TouchStation does not bundle Sony firmware or game data.")
    }

    private fun settings() {
        currentPage = "Settings"
        page("Settings", "controller and application information")
        val pads = InputDevice.getDeviceIds().mapNotNull { InputDevice.getDevice(it) }
            .filter {
                it.sources and (InputDevice.SOURCE_GAMEPAD or InputDevice.SOURCE_JOYSTICK) != 0
            }
        card("CONNECTED CONTROLLERS", if (pads.isEmpty()) {
            "no game controller detected"
        } else {
            pads.joinToString("\n") { it.name }
        })
        card("APPLICATION", "TouchStation PS3 2.0.0\nAndroid frontend · min Android 8.0")
        card("ENGINE COMPONENTS", "PPU: not linked\nSPU: not linked\nRSX/Vulkan: not linked\nFirmware installer: not linked\nGame boot: unavailable")
        card("IMPORT MODEL", "only two user-selected inputs are required by this frontend: one game file and PS3UPDATE.PUP. no keys, BIOS files, or external data packs are requested.")
    }

    private fun pick(requestCode: Int) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "*/*"
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        }
        startActivityForResult(intent, requestCode)
    }

    @Deprecated("Legacy result API retained for broad Android compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode != RESULT_OK || data?.data == null) return
        val uri = data.data!!
        val flags = data.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION
        try {
            contentResolver.takePersistableUriPermission(uri, flags)
        } catch (_: Exception) {
            // Some document providers do not offer persistable grants.
        }

        when (requestCode) {
            100 -> {
                val ext = extension(uri)
                if (ext !in setOf("iso", "pkg", "self", "elf")) {
                    Toast.makeText(this, "unsupported game file. choose ISO, PKG, SELF, or ELF.", Toast.LENGTH_LONG).show()
                    return
                }
                game = uri
                prefs.edit().putString("game_uri", uri.toString()).apply()
                library()
            }
            101 -> {
                if (extension(uri) != "pup" || !isValidPup(uri)) {
                    Toast.makeText(this, "that file is not recognised as a PS3 PUP firmware package.", Toast.LENGTH_LONG).show()
                    return
                }
                firmware = uri
                prefs.edit().putString("firmware_uri", uri.toString()).apply()
                firmwarePage()
            }
        }
    }

    private fun displayName(uri: Uri): String {
        var result = uri.lastPathSegment ?: "selected file"
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) result = cursor.getString(0) ?: result
        }
        return result
    }

    private fun extension(uri: Uri): String =
        displayName(uri).substringAfterLast('.', "").lowercase(Locale.US)

    private fun fileSummary(uri: Uri): String {
        val size = contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else null
        }
        return size?.let { "size: ${formatBytes(it)}" } ?: "size unavailable"
    }

    private fun formatBytes(bytes: Long): String = when {
        bytes >= 1_073_741_824L -> String.format(Locale.US, "%.2f GB", bytes / 1_073_741_824.0)
        bytes >= 1_048_576L -> String.format(Locale.US, "%.1f MB", bytes / 1_048_576.0)
        bytes >= 1_024L -> String.format(Locale.US, "%.1f KB", bytes / 1_024.0)
        else -> "$bytes bytes"
    }

    private fun isValidPup(uri: Uri): Boolean = try {
        contentResolver.openInputStream(uri)?.use { input ->
            val header = ByteArray(4)
            var offset = 0
            while (offset < header.size) {
                val read = input.read(header, offset, header.size - offset)
                if (read <= 0) return@use false
                offset += read
            }
            header.contentEquals(byteArrayOf(0x53, 0x43, 0x45, 0x00))
        } ?: false
    } catch (_: Exception) {
        false
    }

    override fun onBackPressed() {
        if (currentPage != "Home") home() else super.onBackPressed()
    }
}
