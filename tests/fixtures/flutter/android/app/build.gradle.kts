plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.example.flutter_app"
    compileSdk = flutter.compileSdkVersion

    defaultConfig {
        applicationId = "com.example.flutter_app"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
    }
}
