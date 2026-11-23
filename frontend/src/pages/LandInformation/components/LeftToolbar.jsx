import {
  Image,
  Layers3,
  Map,
  Pentagon,
  PlugZap,
  Wrench,
} from 'lucide-react';

const tools = [
  { id: 'layers', label: 'Layer manager', Icon: Layers3 },
  { id: 'tools', label: 'Map tools', Icon: Wrench },
  { id: 'boundaries', label: 'Administrative boundaries', Icon: Pentagon },
  { id: 'imagery', label: 'Map imagery', Icon: Image },
  { id: 'connections', label: 'Map connections', Icon: PlugZap },
  { id: 'map', label: 'Map view', Icon: Map },
];

export default function LeftToolbar({ activeTool, onToolChange }) {
  return (
    <nav
      className="absolute left-3 top-6 z-20 flex flex-col gap-1.5 rounded-xl bg-[#062d24]/95 p-1.5 shadow-xl ring-1 ring-white/10 max-sm:left-2 max-sm:top-3"
      aria-label="Map tools"
    >
      {tools.map(({ id, label, Icon }) => (
        <button
          key={id}
          type="button"
          className={`grid h-11 w-11 place-items-center rounded-lg border transition-colors max-sm:h-10 max-sm:w-10 ${
            activeTool === id
              ? 'border-emerald-500 bg-emerald-700 text-white shadow-inner'
              : 'border-transparent bg-transparent text-emerald-50 hover:bg-emerald-800'
          }`}
          aria-label={label}
          aria-pressed={activeTool === id}
          title={label}
          onClick={() => onToolChange(id)}
        >
          <Icon size={21} strokeWidth={2.2} />
        </button>
      ))}
    </nav>
  );
}
