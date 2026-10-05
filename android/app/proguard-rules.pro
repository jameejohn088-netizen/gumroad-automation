# Keep DTOs used by Gson/Retrofit.
-keep class com.gumroadautomation.data.api.dto.** { *; }
# Keep Room entities (referenced via reflection-free generated code, but safe).
-keep class com.gumroadautomation.data.db.entity.** { *; }
# Retrofit / OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keepattributes Signature, InnerClasses, EnclosingMethod
