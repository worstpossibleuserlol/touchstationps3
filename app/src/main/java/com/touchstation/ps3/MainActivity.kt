package com.touchstation.ps3

import android.app.Activity
import android.os.Bundle
import android.content.Intent
import android.net.Uri
import android.view.Gravity
import android.widget.*
import android.graphics.Typeface
import android.graphics.Color
import android.content.Context
import android.view.InputDevice

class MainActivity : Activity() {
    private lateinit var root: LinearLayout
    private lateinit var content: LinearLayout
    private val prefs by lazy { getSharedPreferences("touchstation", Context.MODE_PRIVATE) }
    private var game: Uri? = null
    private var firmware: Uri? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        game = prefs.getString("game", null)?.let(Uri::parse)
        firmware = prefs.getString("firmware", null)?.let(Uri::parse)
        home()
    }
    private fun layout(title: String, subtitle: String) {
        root = LinearLayout(this).apply { orientation=1; setPadding(22,28,22,18); setBackgroundColor(Color.rgb(12,17,29)) }
        root.addView(TextView(this).apply { text=title; textSize=27f; setTextColor(Color.WHITE); typeface=Typeface.DEFAULT_BOLD })
        root.addView(TextView(this).apply { text=subtitle; textSize=14f; setTextColor(Color.LTGRAY); setPadding(0,5,0,22) })
        content=LinearLayout(this).apply { orientation=1 }
        root.addView(content,LinearLayout.LayoutParams(-1,0,1f))
        val nav=LinearLayout(this).apply { gravity=Gravity.CENTER }
        listOf("Home","Library","Firmware","System").forEach { label ->
            nav.addView(Button(this).apply { text=label; textSize=10f; setOnClickListener { when(label) { "Home"->home(); "Library"->library(); "Firmware"->firmwarePage(); else->system() } } },LinearLayout.LayoutParams(0,-2,1f))
        }
        root.addView(nav); setContentView(root)
    }
    private fun card(title:String, body:String) {
        val box=LinearLayout(this).apply { orientation=1; setPadding(16,14,16,14); setBackgroundColor(Color.rgb(27,37,55)) }
        box.addView(TextView(this).apply { text=title; textSize=17f; typeface=Typeface.DEFAULT_BOLD; setTextColor(Color.WHITE) })
        box.addView(TextView(this).apply { text=body; textSize=13f; setTextColor(Color.LTGRAY); setPadding(0,7,0,0) })
        content.addView(box,LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=12 })
    }
    private fun button(label:String, fn:()->Unit) {
        content.addView(Button(this).apply { text=label; setOnClickListener { fn() } },LinearLayout.LayoutParams(-1,-2).apply { bottomMargin=8 })
    }
    private fun home() {
        layout("TouchStation PS3","PlayStation 3 library and system manager")
        card("Game",game?.let(::name) ?: "No game selected")
        card("System software",firmware?.let(::name) ?: "PS3UPDATE.PUP not selected")
        card("Status","File manager ready. PS3 game execution is not available.")
        button("Import game") { library() }; button("Import firmware") { firmwarePage() }
    }
    private fun library() {
        layout("Game library","Choose a game file from device storage")
        card("Selected game",game?.let(::name) ?: "Nothing imported")
        button("Choose game file") { pick(100) }
        button("Clear game") { game=null; prefs.edit().remove("game").apply(); library() }
        card("Formats","ELF, SELF and ISO files can be selected. Selection does not imply executable compatibility.")
    }
    private fun firmwarePage() {
        layout("System software","Select your legally obtained PS3UPDATE.PUP")
        card("Firmware",firmware?.let(::name) ?: "No firmware selected")
        button("Choose PS3UPDATE.PUP") { pick(101) }
        button("Clear firmware") { firmware=null; prefs.edit().remove("firmware").apply(); firmwarePage() }
        card("Firmware handling","This app stores the selected file reference. It does not install or emulate Sony system software.")
    }
    private fun system() {
        layout("System","Controller and application information")
        val pads=InputDevice.getDeviceIds().mapNotNull(InputDevice::getDevice).filter { it.sources and (InputDevice.SOURCE_GAMEPAD or InputDevice.SOURCE_JOYSTICK)!=0 }
        card("Controllers",if(pads.isEmpty()) "No controller detected" else pads.joinToString("\n"){it.name})
        card("Version","TouchStation PS3 1.0.2")
        card("About","Android frontend for PS3 file organization. PPU/SPU execution, RSX graphics and game boot are not implemented.")
    }
    private fun pick(code:Int) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type="*/*" },code)
    }
    @Deprecated("Legacy result API for compatibility")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(resultCode!=RESULT_OK) return
        val uri=data?.data ?: return
        try { contentResolver.takePersistableUriPermission(uri,Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_:Exception) {}
        if(requestCode==100) { game=uri; prefs.edit().putString("game",uri.toString()).apply(); library() }
        if(requestCode==101) { firmware=uri; prefs.edit().putString("firmware",uri.toString()).apply(); firmwarePage() }
    }
    private fun name(uri:Uri):String {
        var result=uri.lastPathSegment ?: "Selected file"
        contentResolver.query(uri,arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),null,null,null)?.use { if(it.moveToFirst()) result=it.getString(0) ?: result }
        return result
    }
}