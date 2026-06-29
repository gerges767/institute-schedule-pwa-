// Service Worker - نظام إدارة جداول المحاضرات
// تطوير المهندس: Mokhtar Gerges © 2026

const CACHE_NAME = 'institute-schedule-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/js/app.js',
  '/static/icons/icon-48x48.png',
  '/static/icons/icon-72x72.png',
  '/static/icons/icon-96x96.png',
  '/static/icons/icon-144x144.png',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/manifest.json'
];

// تثبيت Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => {
      return self.skipWaiting();
    })
  );
});

// تفعيل Service Worker
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// استراتيجية الجلب: Cache First, then Network
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API requests - Network First
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // تخزين الاستجابة في الكاش
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, clone);
          });
          return response;
        })
        .catch(() => {
          return caches.match(request);
        })
    );
    return;
  }

  // Static assets - Cache First
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        if (!response || response.status !== 200 || response.type !== 'basic') {
          return response;
        }
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(request, clone);
        });
        return response;
      });
    })
  );
});

// إشعارات الدفع (Push Notifications)
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'تنبيه المحاضرات';
  const options = {
    body: data.body || 'لديك محاضرة قادمة!',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    dir: 'rtl',
    lang: 'ar',
    vibrate: [200, 100, 200],
    requireInteraction: true,
    actions: [
      { action: 'open', title: 'فتح التطبيق' },
      { action: 'dismiss', title: 'تجاهل' }
    ],
    data: data
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// النقر على الإشعار
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.matchAll({ type: 'window' }).then((clientList) => {
        if (clientList.length > 0) {
          clientList[0].focus();
          clientList[0].navigate('/');
        } else {
          clients.openWindow('/');
        }
      })
    );
  }
});

// مزامنة في الخلفية
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-schedule') {
    event.waitUntil(syncScheduleData());
  }
});

async function syncScheduleData() {
  // مزامنة البيانات المخزنة محلياً مع السيرفر
  const pending = await getPendingActions();
  for (const action of pending) {
    try {
      await fetch(action.url, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action.data)
      });
      await removePendingAction(action.id);
    } catch (e) {
      console.error('Sync failed:', e);
    }
  }
}

// IndexedDB helpers
function getPendingActions() {
  return new Promise((resolve) => {
    const request = indexedDB.open('institute-db', 1);
    request.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('pending')) {
        db.createObjectStore('pending', { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = (e) => {
      const db = e.target.result;
      const tx = db.transaction('pending', 'readonly');
      const store = tx.objectStore('pending');
      const getAll = store.getAll();
      getAll.onsuccess = () => resolve(getAll.result);
    };
    request.onerror = () => resolve([]);
  });
}

function removePendingAction(id) {
  return new Promise((resolve) => {
    const request = indexedDB.open('institute-db', 1);
    request.onsuccess = (e) => {
      const db = e.target.result;
      const tx = db.transaction('pending', 'readwrite');
      const store = tx.objectStore('pending');
      store.delete(id);
      tx.oncomplete = resolve;
    };
    request.onerror = resolve;
  });
}
