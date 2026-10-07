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
if (iconSrcDir.isDirectory) {
    for (f in iconSrcDir.walkTopDown()) {
        if (!f.isFile || !f.name.endsWith(".b64")) continue
        val relPath = f.relativeTo(iconSrcDir).invariantSeparatorsPath.removeSuffix(".b64")
        val out = iconResDir.resolve(relPath)
        out.parentFile.mkdirs()
        out.writeBytes(java.util.Base64.getMimeDecoder().decode(f.readText().trim()))
    }
}
