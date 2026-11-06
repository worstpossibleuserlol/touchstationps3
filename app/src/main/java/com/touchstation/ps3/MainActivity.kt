package com.touchstation.ps3

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.InputDevice
import android.view.View
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.util.Locale

class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("touchstation", Context.MODE_PRIVATE) }
    private var game: Uri? = null
    private var firmware: Uri? = null

    private lateinit var root: LinearLayout
    private lateinit var pageContent: LinearLayout
    private var currentPage = "Home"

    private val backgroundColor = Color.rgb(7, 10, 17)
    private val panelColor = Color.rgb(17, 24, 37)
    private val raisedPanelColor = Color.rgb(24, 34, 51)
    private val primaryBlue = Color.rgb(43, 116, 246)
    private val brightBlue = Color.rgb(80, 148, 255)
    private val primaryText = Color.rgb(245, 247, 251)
    private val secondaryText = Color.rgb(151, 164, 185)
    private val dividerColor = Color.rgb(39, 52, 74)
    private val green = Color.rgb(72, 205, 145)
    private val amber = Color.rgb(244, 184, 82)
    private val red = Color.rgb(255, 107, 120)

    private val logoBitmap by lazy {
        runCatching {
            val encoded = resources.openRawResource(R.raw.touchstation_logo)
                .bufferedReader()
                .use { it.readText().trim() }
            val bytes = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT)
            BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        }.getOrNull()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = backgroundColor
        window.navigationBarColor = backgroundColor
        window.decorView.systemUiVisibility = 0

        game = prefs.getString("game_uri", null)?.let(Uri::parse)
        firmware = prefs.getString("firmware_uri", null)?.let(Uri::parse)
        home()
    }

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()

    private fun rounded(
        color: Int,
        radius: Int = 18,
        stroke: Int = Color.TRANSPARENT
    ): GradientDrawable = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        setColor(color)
        cornerRadius = dp(radius).toFloat()
        if (stroke != Color.TRANSPARENT) setStroke(dp(1), stroke)
    }

    private fun label(
        value: String,
        size: Float = 14f,
        color: Int = primaryText,
        bold: Boolean = false
    ): TextView = TextView(this).apply {
        text = value
        textSize = size
        setTextColor(color)
        typeface = if (bold) Typeface.create("sans-serif", Typeface.BOLD)
        else Typeface.create("sans-serif", Typeface.NORMAL)
        setLineSpacing(dp(2).toFloat(), 1f)
    }

    private fun addLabel(
        parent: LinearLayout,
        value: String,
        size: Float = 14f,
        color: Int = primaryText,
        bold: Boolean = false
    ): TextView {
        val view = label(value, size, color, bold)
        parent.addView(view, LinearLayout.LayoutParams(-1, -2))
        return view
    }

    private fun gap(parent: LinearLayout, height: Int) {
        parent.addView(View(this), LinearLayout.LayoutParams(1, dp(height)))
    }

    private fun panel(
        parent: LinearLayout,
        padding: Int = 17,
        outlined: Boolean = false
    ): LinearLayout {
        val view = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(padding), dp(padding), dp(padding), dp(padding))
            background = rounded(panelColor, 18, if (outlined) dividerColor else Color.TRANSPARENT)
        }
        parent.addView(view, LinearLayout.LayoutParams(-1, -2).apply {
            bottomMargin = dp(12)
        })
        return view
    }

    private fun section(parent: LinearLayout, value: String) {
        val title = label(value.uppercase(Locale.US), 10f, secondaryText, true)
        title.letterSpacing = 0.12f
        parent.addView(title, LinearLayout.LayoutParams(-1, -2).apply {
            topMargin = dp(7)
            bottomMargin = dp(9)
        })
    }

    private fun pill(parent: LinearLayout, value: String, color: Int) {
        val chip = TextView(this).apply {
            text = value.uppercase(Locale.US)
            textSize = 9.5f
            letterSpacing = 0.08f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setTextColor(color)
            setPadding(dp(10), dp(7), dp(10), dp(7))
            background = rounded(
                Color.argb(32, Color.red(color), Color.green(color), Color.blue(color)),
                20
            )
        }
        parent.addView(chip, LinearLayout.LayoutParams(-2, -2))
    }

    private fun actionButton(
        parent: LinearLayout,
        value: String,
        primary: Boolean = true,
        enabled: Boolean = true,
        action: () -> Unit
    ) {
        val button = Button(this).apply {
            text = value
            isAllCaps = false
            textSize = 14f
            typeface = Typeface.create("sans-serif", Typeface.BOLD)
            setTextColor(if (primary) Color.WHITE else primaryText)
            background = rounded(
                if (primary) primaryBlue else raisedPanelColor,
                14,
                if (primary) Color.TRANSPARENT else dividerColor
            )
            isEnabled = enabled
            alpha = if (enabled) 1f else 0.45f
            stateListAnimator = null
            setOnClickListener { if (enabled) action() }
        }
        parent.addView(button, LinearLayout.LayoutParams(-1, dp(52)).apply {
            bottomMargin = dp(9)
        })
    }

    private fun setupRow(
        parent: LinearLayout,
        number: String,
        title: String,
        description: String,
        done: Boolean
    ) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val numberView = TextView(this).apply {
            text = if (done) "✓" else number
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
            gravity = Gravity.CENTER
            setTextColor(if (done) green else secondaryText)
            background = rounded(
                if (done) Color.rgb(20, 57, 49) else raisedPanelColor,
                13
            )
        }
        row.addView(numberView, LinearLayout.LayoutParams(dp(38), dp(38)))
        val copy = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), 0, dp(8), 0)
        }
        copy.addView(label(title, 13f, primaryText, true))
        copy.addView(label(description, 11f, secondaryText))
        row.addView(copy, LinearLayout.LayoutParams(0, -2, 1f))
        val state = label(if (done) "ADDED" else "NEEDED", 9f, if (done) green else secondaryText, true)
        state.letterSpacing = 0.06f
        row.addView(state)
        parent.addView(row, LinearLayout.LayoutParams(-1, -2))
    }

    private fun shell(active: String, title: String, subtitle: String) {
        currentPage = active
        root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(18), dp(11), dp(18), dp(9))
            setBackgroundColor(backgroundColor)
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val logo = ImageView(this).apply {
            setImageBitmap(logoBitmap)
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = "TouchStation PS3"
        }
        header.addView(logo, LinearLayout.LayoutParams(dp(76), dp(66)))

        val brand = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(10), 0, 0, 0)
        }
        brand.addView(label("TouchStation", 16f, primaryText, true))
        val subBrand = label("PLAYSTATION 3", 9f, brightBlue, true)
        subBrand.letterSpacing = 0.18f
        brand.addView(subBrand)
        header.addView(brand, LinearLayout.LayoutParams(0, -2, 1f))

        val version = TextView(this).apply {
            text = "v2.0.0"
            textSize = 10f
            setTextColor(secondaryText)
            setPadding(dp(10), dp(7), dp(10), dp(7))
            background = rounded(raisedPanelColor, 20, dividerColor)
        }
        header.addView(version)
        root.addView(header)

        val divider = View(this).apply { setBackgroundColor(dividerColor) }
        root.addView(divider, LinearLayout.LayoutParams(-1, dp(1)).apply {
            topMargin = dp(9)
            bottomMargin = dp(17)
        })

        val scroll = ScrollView(this).apply {
            isFillViewport = true
            overScrollMode = View.OVER_SCROLL_NEVER
        }
        pageContent = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(1), 0, dp(1), dp(12))
        }
        scroll.addView(pageContent)
        addLabel(pageContent, title, 25f, primaryText, true)
        gap(pageContent, 4)
        addLabel(pageContent, subtitle, 12f, secondaryText)
        gap(pageContent, 18)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))

        val nav = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
            setPadding(dp(4), dp(4), dp(4), dp(4))
            background = rounded(panelColor, 17, dividerColor)
        }
        listOf("Home", "Library", "Firmware", "Settings").forEach { destination ->
            val item = TextView(this).apply {
                text = destination.uppercase(Locale.US)
                textSize = 9f
                letterSpacing = 0.06f
                gravity = Gravity.CENTER
                typeface = Typeface.create("sans-serif", Typeface.BOLD)
                setTextColor(if (destination == active) Color.WHITE else secondaryText)
                background = if (destination == active) rounded(primaryBlue, 12) else null
                setPadding(dp(5), dp(13), dp(5), dp(13))
                setOnClickListener {
                    when (destination) {
                        "Home" -> home()
                        "Library" -> library()
                        "Firmware" -> firmwarePage()
                        else -> settings()
                    }
                }
            }
            nav.addView(item, LinearLayout.LayoutParams(0, -1, 1f).apply {
                marginEnd = dp(3)
                marginStart = dp(3)
            })
        }
        root.addView(nav, LinearLayout.LayoutParams(-1, dp(49)))
        setContentView(root)
    }

    private fun home() {
        val gameName = game?.let(::displayName)
        val firmwareName = firmware?.let(::displayName)
        val hasValidFirmware = firmware?.let(::isValidPup) == true

        shell("Home", "Your PS3 library", "Everything for your console, in one place.")

        val hero = panel(pageContent, 19, true)
        hero.background = GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            intArrayOf(Color.rgb(23, 43, 76), Color.rgb(17, 25, 40))
        ).apply {
            cornerRadius = dp(19).toFloat()
            setStroke(dp(1), Color.rgb(42, 78, 128))
        }
        val heroEyebrow = label("TOUCHSTATION  /  PS3", 9.5f, brightBlue, true)
        heroEyebrow.letterSpacing = 0.15f
        hero.addView(heroEyebrow)
        gap(hero, 10)
        hero.addView(label("Your games. Your console.", 22f, primaryText, true))
        gap(hero, 7)
        hero.addView(label(
            "Bring in your PS3 game and original system software to prepare your library.",
            12f,
            Color.rgb(190, 202, 220)
        ))
        gap(hero, 15)
        pill(hero, "2 required files · local storage", brightBlue)

        section(pageContent, "Console setup")
        val setup = panel(pageContent, 16, true)
        setupRow(setup, "01", "PS3 game", gameName ?: "Choose an ISO, PKG, SELF or ELF file", game != null)
        gap(setup, 15)
        val line = View(this).apply { setBackgroundColor(dividerColor) }
        setup.addView(line, LinearLayout.LayoutParams(-1, dp(1)))
        gap(setup, 15)
        setupRow(
            setup,
            "02",
            "System software",
            firmwareName ?: "Choose your official PS3UPDAT.PUP",
            hasValidFirmware
        )
        gap(setup, 12)
        actionButton(setup, if (game == null) "Import game file" else "Replace game file") { pick(100) }
        actionButton(setup, if (firmware == null) "Import system software" else "Replace system software", false) {
            pick(101)
        }

        section(pageContent, "Engine status")
        val engine = panel(pageContent, 16, true)
        val engineHeader = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        engineHeader.addView(label("PS3 emulation core", 14f, primaryText, true),
            LinearLayout.LayoutParams(0, -2, 1f))
        pill(engineHeader, "Not linked", amber)
        engine.addView(engineHeader)
        gap(engine, 8)
        engine.addView(label(
            "This repository currently contains the TouchStation Android frontend and import manager. PPU/SPU execution, RSX rendering, firmware installation and game boot are not connected yet.",
            12f,
            secondaryText
        ))

        section(pageContent, "Your files")
        val filePanel = panel(pageContent)
        addLabel(filePanel, "GAME", 9f, secondaryText, true)
        gap(filePanel, 3)
        addLabel(filePanel, gameName ?: "No game imported", 13f, if (game != null) primaryText else secondaryText, game != null)
        gap(filePanel, 11)
        addLabel(filePanel, "FIRMWARE", 9f, secondaryText, true)
        gap(filePanel, 3)
        addLabel(filePanel, firmwareName ?: "No firmware imported", 13f, if (hasValidFirmware) primaryText else secondaryText, hasValidFirmware)
        gap(filePanel, 5)
        addLabel(
            filePanel,
            if (game != null && hasValidFirmware) {
                "Both files are saved as document references on this device."
            } else {
                "Import either file at any time. You can replace or remove it later."
            },
            11f,
            secondaryText
        )
    }

    private fun library() {
        shell("Library", "Game library", "Manage the PS3 game file you selected.")
        section(pageContent, "Selected game")

        val current = game
        if (current == null) {
            val empty = panel(pageContent, 20, true)
            pill(empty, "No game yet", secondaryText)
            gap(empty, 12)
            addLabel(empty, "Your library is waiting.", 18f, primaryText, true)
            gap(empty, 5)
            addLabel(empty, "Import a PS3 disc image or package. TouchStation remembers the file selection on this device.", 12f, secondaryText)
        } else {
            val details = panel(pageContent, 18, true)
            pill(details, "Game imported", green)
            gap(details, 12)
            addLabel(details, displayName(current), 17f, primaryText, true)
            gap(details, 5)
            addLabel(details, fileSummary(current), 12f, secondaryText)
            gap(details, 4)
            addLabel(details, "Format: ${extension(current).uppercase(Locale.US)}", 11f, brightBlue, true)
            gap(details, 12)
            actionButton(details, "Replace game file") { pick(100) }
            actionButton(details, "Remove game", false) {
                clearImportedFile(current, "game_uri")
                game = null
                library()
            }
        }

        section(pageContent, "Supported imports")
        val formats = panel(pageContent)
        addLabel(formats, "ISO  ·  PKG  ·  SELF  ·  ELF", 14f, primaryText, true)
        gap(formats, 5)
        addLabel(formats, "Select one game file. This screen does not yet install packages or boot games; that requires the native PS3 engine.", 12f, secondaryText)
        gap(pageContent, 4)
        actionButton(pageContent, if (game == null) "Choose game file" else "Choose another game") {
            pick(100)
        }
    }

    private fun firmwarePage() {
        shell("Firmware", "System software", "Import the official PS3 update package.")
        section(pageContent, "Firmware package")

        val current = firmware
        val valid = current?.let(::isValidPup) == true
        val info = panel(pageContent, 18, true)
        when {
            current == null -> {
                pill(info, "Not imported", secondaryText)
                gap(info, 12)
                addLabel(info, "PS3UPDATE.PUP", 17f, primaryText, true)
                gap(info, 5)
                addLabel(info, "Choose the official system update package from your device.", 12f, secondaryText)
            }
            valid -> {
                pill(info, "PUP header recognised", green)
                gap(info, 12)
                addLabel(info, displayName(current), 16f, primaryText, true)
                gap(info, 5)
                addLabel(info, fileSummary(current), 12f, secondaryText)
                gap(info, 6)
                addLabel(info, "The file header is recognised. This is not a full integrity check or firmware installation.", 11f, secondaryText)
                gap(info, 12)
                actionButton(info, "Replace firmware") { pick(101) }
                actionButton(info, "Remove firmware", false) {
                    clearImportedFile(current, "firmware_uri")
                    firmware = null
                    firmwarePage()
                }
            }
            else -> {
                pill(info, "File not recognised", red)
                gap(info, 12)
                addLabel(info, displayName(current), 16f, primaryText, true)
                gap(info, 5)
                addLabel(info, "The selected file does not have the expected SCE PUP header. Choose the official PS3UPDATE.PUP package.", 12f, secondaryText)
                gap(info, 12)
                actionButton(info, "Choose firmware again") { pick(101) }
                actionButton(info, "Remove file", false) {
                    clearImportedFile(current, "firmware_uri")
                    firmware = null
                    firmwarePage()
                }
            }
        }

        section(pageContent, "About firmware")
        val note = panel(pageContent)
        addLabel(note, "Your system software stays yours.", 14f, primaryText, true)
        gap(note, 6)
        addLabel(note, "TouchStation does not include or redistribute Sony firmware. The current frontend can identify the PUP header and remember your file selection; decrypting and installing firmware is not available until an emulator core is integrated.", 12f, secondaryText)
    }

    private fun settings() {
        shell("Settings", "Settings", "A few details about this build and your device.")

        section(pageContent, "Controller")
        val controllers = InputDevice.getDeviceIds()
            .mapNotNull { id -> InputDevice.getDevice(id) }
            .filter { device ->
                device.sources and (InputDevice.SOURCE_GAMEPAD or InputDevice.SOURCE_JOYSTICK) != 0
            }

        val controllerPanel = panel(pageContent)
        pill(controllerPanel, if (controllers.isEmpty()) "No controller detected" else "${controllers.size} connected", if (controllers.isEmpty()) secondaryText else green)
        gap(controllerPanel, 10)
        addLabel(
            controllerPanel,
            if (controllers.isEmpty()) {
                "Connect a USB or Bluetooth controller to Android. Detection is shown here; emulator input mapping is not active in this frontend build."
            } else {
                controllers.joinToString("\n") { it.name }
            },
            12f,
            secondaryText
        )

        section(pageContent, "Emulator components")
        val enginePanel = panel(pageContent, 16, true)
        addEngineLine(enginePanel, "PPU execution", false)
        addEngineLine(enginePanel, "SPU execution", false)
        addEngineLine(enginePanel, "RSX / Vulkan renderer", false)
        addEngineLine(enginePanel, "PS3 firmware installer", false)
        addEngineLine(enginePanel, "Game boot", false)

        section(pageContent, "Application")
        val appPanel = panel(pageContent)
        addLabel(appPanel, "TouchStation PS3", 14f, primaryText, true)
        gap(appPanel, 4)
        addLabel(appPanel, "Version 2.0.0 · Android frontend", 11f, brightBlue, true)
        gap(appPanel, 8)
        addLabel(appPanel, "Only your game file and official PS3 firmware are requested by the current import flow. No system firmware or commercial games are bundled.", 12f, secondaryText)
    }

    private fun addEngineLine(parent: LinearLayout, title: String, active: Boolean) {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(0, dp(7), 0, dp(7))
        }
        row.addView(label(title, 12f, primaryText), LinearLayout.LayoutParams(0, -2, 1f))
        row.addView(label(if (active) "CONNECTED" else "NOT LINKED", 9f, if (active) green else amber, true))
        parent.addView(row)
        val divider = View(this).apply { setBackgroundColor(dividerColor) }
        parent.addView(divider, LinearLayout.LayoutParams(-1, dp(1)))
    }

    private fun clearImportedFile(uri: Uri, key: String) {
        runCatching {
            contentResolver.releasePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        prefs.edit().remove(key).apply()
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
        val grantedFlags = data.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION
        runCatching {
            contentResolver.takePersistableUriPermission(uri, grantedFlags)
        }

        when (requestCode) {
            100 -> {
                val ext = extension(uri)
                if (ext !in setOf("iso", "pkg", "self", "elf")) {
                    Toast.makeText(
                        this,
                        "Unsupported game file. Choose ISO, PKG, SELF or ELF.",
                        Toast.LENGTH_LONG
                    ).show()
                    return
                }
                game = uri
                prefs.edit().putString("game_uri", uri.toString()).apply()
                library()
            }
            101 -> {
                if (extension(uri) != "pup" || !isValidPup(uri)) {
                    Toast.makeText(
                        this,
                        "That file is not recognised as a PS3 PUP package.",
                        Toast.LENGTH_LONG
                    ).show()
                    return
                }
                firmware = uri
                prefs.edit().putString("firmware_uri", uri.toString()).apply()
                firmwarePage()
            }
        }
    }

    private fun displayName(uri: Uri): String {
        var result = uri.lastPathSegment?.substringAfterLast('/') ?: "Selected file"
        runCatching {
            contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) result = cursor.getString(index) ?: result
                }
            }
        }
        return result
    }

    private fun extension(uri: Uri): String =
        displayName(uri).substringAfterLast('.', "").lowercase(Locale.US)

    private fun fileSummary(uri: Uri): String {
        val size = runCatching {
            contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (index >= 0 && !cursor.isNull(index)) cursor.getLong(index) else null
                } else null
            }
        }.getOrNull()
        return size?.let { "Size: ${formatBytes(it)}" } ?: "Size unavailable"
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
