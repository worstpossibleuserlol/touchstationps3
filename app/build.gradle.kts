plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "com.touchstation.ps3"
    compileSdk = 35
    defaultConfig { applicationId = "com.touchstation.ps3"; minSdk = 26; targetSdk = 35; versionCode = 102; versionName = "1.0.2" }
}