import { House, LogOut, Printer } from 'lucide-react';

export default function LandSubHeader() {
  return (
    <header className="z-30 flex h-[66px] shrink-0 items-center justify-between border-b border-emerald-950 bg-[#064536] px-6 shadow-md max-sm:h-[60px] max-sm:px-3">
      <div className="flex min-w-0 items-center gap-3">
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-2 border-white/80 bg-white text-[#07513e] shadow-sm max-sm:h-9 max-sm:w-9">
          <span className="font-serif text-2xl font-black">R</span>
        </div>
        <h1 className="truncate font-sans text-[21px] font-semibold tracking-wide text-white max-sm:text-sm">
          RUDA LAND INFORMATION SYSTEM
        </h1>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="flex h-10 items-center gap-2 rounded-lg border border-white/20 bg-white/10 px-3 text-xs font-bold text-white hover:bg-white/20 max-sm:h-9 max-sm:px-2"
          onClick={() => window.print()}
          aria-label="Print map"
        >
          <Printer size={16} />
          <span className="max-sm:hidden">PRINT</span>
        </button>
        <a
          href="/"
          className="grid h-10 w-10 place-items-center rounded-lg border border-white/20 bg-white/10 text-white hover:bg-white/20 max-sm:h-9 max-sm:w-9"
          aria-label="Home"
          title="Home"
        >
          <House size={17} />
        </a>
        <a
          href="/"
          className="grid h-10 w-10 place-items-center rounded-lg border border-white/20 bg-white/10 text-white hover:bg-white/20 max-sm:h-9 max-sm:w-9"
          aria-label="Exit map"
          title="Exit map"
        >
          <LogOut size={17} />
        </a>
      </div>
    </header>
  );
}
