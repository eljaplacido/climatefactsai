import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[70vh] flex items-center justify-center bg-gray-50 dark:bg-slate-900 px-4 py-16">
      <div className="max-w-lg w-full bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 p-8 sm:p-10 text-center space-y-6">
        <Link
          href="/"
          className="inline-block text-2xl font-bold text-clilens-primary dark:text-teal-400"
        >
          Climatefacts.ai
        </Link>

        <div className="space-y-3">
          <p className="text-6xl font-bold text-clilens-primary dark:text-teal-400 leading-none">
            404
          </p>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">
            Page not found
          </h1>
          <p className="text-gray-600 dark:text-slate-400">
            The article or page you&rsquo;re looking for may have been moved or
            deleted.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
          <Link
            href="/"
            className="px-5 py-2.5 rounded-lg bg-clilens-primary text-white font-medium hover:bg-clilens-teal-600 transition-colors"
          >
            Home
          </Link>
          <Link
            href="/search"
            className="px-5 py-2.5 rounded-lg border border-gray-200 dark:border-slate-600 text-gray-700 dark:text-slate-200 font-medium hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
          >
            Search
          </Link>
          <Link
            href="/map"
            className="px-5 py-2.5 rounded-lg border border-gray-200 dark:border-slate-600 text-gray-700 dark:text-slate-200 font-medium hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
          >
            Map
          </Link>
          <Link
            href="/methodology"
            className="px-5 py-2.5 rounded-lg border border-gray-200 dark:border-slate-600 text-gray-700 dark:text-slate-200 font-medium hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors"
          >
            Methodology
          </Link>
        </div>
      </div>
    </div>
  );
}
