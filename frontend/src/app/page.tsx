export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <section className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wider text-sky-700">
          HelpDesk Mini
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-slate-950">
          Project foundation is ready.
        </h1>
        <p className="mt-4 leading-7 text-slate-600">
          Authentication, ticket management, and real-time messaging will be
          added in later milestones.
        </p>
      </section>
    </main>
  );
}
