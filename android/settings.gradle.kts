pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "gumroad-automation"
include(":app")

// App launcher icon: the PNG is stored as base64 text under app/src/main/iconb64
// (binary files can't be pushed through the repo tooling). Decode it here at
// settings time, before any project is configured.
val iconSrcDir = file("app/src/main/iconb64")
val iconResDir = file("app/src/main/res")
val iconB64Files = if (iconSrcDir.isDirectory) {
    iconSrcDir.walkTopDown().filter { it.isFile && it.name.endsWith(".b64") }.toList()
} else emptyList()
println("LAUNCHER_ICON: decoding ${iconB64Files.size} base64 icon files from ${iconSrcDir}")
require(iconB64Files.isNotEmpty()) {
    "LAUNCHER_ICON: no .b64 icon files found in ${iconSrcDir} — refusing to build an APK without the logo"
}
for (f in iconB64Files) {
    val relPath = f.relativeTo(iconSrcDir).invariantSeparatorsPath.removeSuffix(".b64")
    val out = iconResDir.resolve(relPath)
    out.parentFile.mkdirs()
    val bytes = java.util.Base64.getMimeDecoder().decode(f.readText().trim())
    require(bytes.size > 1000 && bytes[0] == 0x89.toByte() && bytes[1] == 0x50.toByte()) {
        "LAUNCHER_ICON: decoded ${f.name} is not a valid PNG (${bytes.size} bytes)"
    }
    out.writeBytes(bytes)
    println("LAUNCHER_ICON: wrote ${out} (${bytes.size} bytes)")
}
