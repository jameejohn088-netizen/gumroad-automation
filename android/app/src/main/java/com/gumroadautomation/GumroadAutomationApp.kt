package com.gumroadautomation

import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

/**
 * Application entry point. Provides the Hilt-backed [Configuration] for WorkManager
 * so [com.gumroadautomation.worker.SyncWorker] can receive injected dependencies.
 */
@HiltAndroidApp
class GumroadAutomationApp : Application(), Configuration.Provider {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()
}
