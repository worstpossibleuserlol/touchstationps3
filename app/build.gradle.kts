plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }
android {
    namespace = "com.touchstation.ps3"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.touchstation.ps3"
        minSdk = 26
        targetSdk = 35
        versionCode = 400
        versionName = "4.0.0"
    }

    // Keep Java and Kotlin bytecode targets aligned. The previous CI build failed
    // because Javac targeted 1.8 while Kotlin targeted 17.
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
