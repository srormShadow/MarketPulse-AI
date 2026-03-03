import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { apiClient } from '../../api/client';
import PredictionSidebar from './PredictionSidebar';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];
const DAY_ABBR = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const CATEGORY_EMOJI = { Snacks: '🍿', Staples: '🌾', 'Edible Oil': '🫙' };

function pad2(n) {
  return String(n).padStart(2, '0');
}

function toDateKey(year, month, day) {
  return `${year}-${pad2(month)}-${pad2(day)}`;
}

function dateKeyFromLocalDate(dateObj) {
  return toDateKey(dateObj.getFullYear(), dateObj.getMonth() + 1, dateObj.getDate());
}

function getDaysInMonth(month, year) {
  return new Date(year, month, 0).getDate();
}

function isPastDay(day, month, year) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const d = new Date(year, month - 1, day);
  return d < today;
}

function isToday(day, month, year) {
  const t = new Date();
  return t.getFullYear() === year && t.getMonth() + 1 === month && t.getDate() === day;
}

function getDaysUntil(dateStr) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${dateStr}T00:00:00`);
  return Math.round((target - today) / 86400000);
}

function getStockUpDate(festivalDateStr, leadTimeDays) {
  const d = new Date(`${festivalDateStr}T00:00:00`);
  d.setDate(d.getDate() - leadTimeDays);
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
}

function formatFullDate(dateStr) {
  const d = new Date(`${dateStr}T00:00:00`);
  return d.toLocaleDateString('en-US', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });
}

function normalizeFestival(item) {
  const name = item?.name || item?.festival_name || 'Festival';
  const categories = Array.isArray(item?.categories)
    ? item.categories
    : (item?.category ? String(item.category).split(',').map((s) => s.trim()).filter(Boolean) : []);
  const demandMultiplier = Number(item?.demand_multiplier);
  const historicalUplift = Number(item?.historical_uplift);
  return {
    ...item,
    festival_name: name,
    name,
    categories,
    demand_multiplier: Number.isFinite(demandMultiplier)
      ? demandMultiplier
      : (Number.isFinite(historicalUplift) ? 1 + historicalUplift : 1),
  };
}

const FESTIVAL_EMOJI = {
  Holi: '🎨',
  Diwali: '🪔',
  Dhanteras: '🪔',
  'Eid ul-Fitr': '🌙',
  'Eid ul-Adha': '🌙',
  Christmas: '⭐',
};

function festivalBadgeContent(festival) {
  const name = festival?.festival_name || festival?.name || '';
  const emoji = FESTIVAL_EMOJI[name];
  if (emoji) {
    return { type: 'emoji', value: emoji };
  }
  const firstLetter = String(name).trim().charAt(0).toUpperCase();
  if (firstLetter) {
    return { type: 'letter', value: firstLetter };
  }
  return { type: 'dot', value: '' };
}

function urgencyBorder(daysUntil) {
  if (daysUntil < 0) return 'border-l-4 border-l-[#475569]';
  if (daysUntil <= 7) return 'border-l-4 border-l-red-500';
  if (daysUntil <= 14) return 'border-l-4 border-l-amber-400';
  return 'border-l-4 border-l-emerald-400';
}

function daysUntilLabel(daysUntil) {
  if (daysUntil < 0) return { text: 'Passed', cls: 'text-[#64748B]' };
  if (daysUntil === 0) return { text: 'Today!', cls: 'text-emerald-400 font-bold' };
  if (daysUntil <= 7) return { text: `${daysUntil} days away`, cls: 'text-red-400' };
  if (daysUntil <= 14) return { text: `${daysUntil} days away`, cls: 'text-amber-400' };
  return { text: `${daysUntil} days away`, cls: 'text-[#94A3B8]' };
}

export default function FestivalCalendar({
  variant = 'compact',
  leadTimes = {},
  onFestivalClick,
}) {
  const today = useMemo(() => new Date(), []);
  const [selectedMonth, setSelectedMonth] = useState(today.getMonth() + 1);
  const [selectedYear, setSelectedYear] = useState(today.getFullYear());
  const [festivals, setFestivals] = useState([]);
  const [allFestivals, setAllFestivals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [highlightedFestival, setHighlightedFestival] = useState(null);

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [isFestival, setIsFestival] = useState(false);
  const [selectedFestivalName, setSelectedFestivalName] = useState(null);

  const stripRef = useRef(null);
  const cardRefs = useRef({});

  const canGoPrev = useMemo(() => {
    const minDate = new Date(today);
    minDate.setMonth(minDate.getMonth() - 3);
    const minMonth = minDate.getMonth() + 1;
    const minYear = minDate.getFullYear();
    if (selectedYear > minYear) return true;
    if (selectedYear === minYear && selectedMonth > minMonth) return true;
    return false;
  }, [selectedMonth, selectedYear, today]);

  const canGoNext = useMemo(() => {
    const maxDate = new Date(today);
    maxDate.setMonth(maxDate.getMonth() + 6);
    const maxMonth = maxDate.getMonth() + 1;
    const maxYear = maxDate.getFullYear();
    if (selectedYear < maxYear) return true;
    if (selectedYear === maxYear && selectedMonth < maxMonth) return true;
    return false;
  }, [selectedMonth, selectedYear, today]);

  const goPrev = useCallback(() => {
    if (!canGoPrev) return;
    setSelectedMonth((m) => {
      if (m === 1) {
        setSelectedYear((y) => y - 1);
        return 12;
      }
      return m - 1;
    });
  }, [canGoPrev]);

  const goNext = useCallback(() => {
    if (!canGoNext) return;
    setSelectedMonth((m) => {
      if (m === 12) {
        setSelectedYear((y) => y + 1);
        return 1;
      }
      return m + 1;
    });
  }, [canGoNext]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient
      .get(`/festivals?month=${selectedMonth}&year=${selectedYear}`)
      .then((res) => {
        if (cancelled) return;
        const items = Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : []);
        setFestivals(items.map(normalizeFestival));
      })
      .catch(() => {
        if (!cancelled) {
          setError('Failed to load festivals');
          setFestivals([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedMonth, selectedYear]);

  useEffect(() => {
    apiClient
      .get('/festivals')
      .then((res) => {
        const items = Array.isArray(res.data?.items) ? res.data.items : (Array.isArray(res.data) ? res.data : []);
        setAllFestivals(items.map(normalizeFestival));
      })
      .catch(() => {
        setAllFestivals([]);
      });
  }, []);

  useEffect(() => {
    if (!stripRef.current) return;
    const todayCell = stripRef.current.querySelector('[data-today="true"]');
    if (todayCell) {
      todayCell.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  }, [selectedMonth, selectedYear, loading]);

  useEffect(() => {
    const el = stripRef.current;
    if (!el) return;

    const handler = (e) => {
      if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
        e.preventDefault();
        el.scrollLeft += e.deltaY;
      }
    };

    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []);

  const numDays = getDaysInMonth(selectedMonth, selectedYear);

  const festivalMap = useMemo(() => {
    const map = {};
    festivals.forEach((f) => {
      const d = new Date(`${f.date}T00:00:00`);
      const day = d.getDate();
      if (!map[day]) {
        map[day] = f;
      }
    });
    return map;
  }, [festivals]);

  const nextFestival = useMemo(() => {
    const todayStr = dateKeyFromLocalDate(today);
    const future = allFestivals
      .filter((f) => f.date >= todayStr)
      .sort((a, b) => a.date.localeCompare(b.date));

    const notThisMonth = future.filter((f) => {
      const d = new Date(`${f.date}T00:00:00`);
      return !(d.getMonth() + 1 === selectedMonth && d.getFullYear() === selectedYear);
    });

    return notThisMonth[0] || future[0] || null;
  }, [allFestivals, selectedMonth, selectedYear, today]);

  const jumpToFestival = useCallback((f) => {
    if (!f?.date) return;
    const d = new Date(`${f.date}T00:00:00`);
    setSelectedMonth(d.getMonth() + 1);
    setSelectedYear(d.getFullYear());
  }, []);

  const openSidebarForDay = useCallback((day, festival) => {
    const isoDate = toDateKey(selectedYear, selectedMonth, day);
    const festivalName = festival?.festival_name || festival?.name || null;

    setSelectedDate(isoDate);
    setIsFestival(Boolean(festival));
    setSelectedFestivalName(festivalName);
    setIsSidebarOpen(true);

    if (festival && onFestivalClick) {
      onFestivalClick(festival);
    }

    if (festivalName) {
      setHighlightedFestival(festivalName);
      const ref = cardRefs.current[festivalName];
      if (ref) ref.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedMonth, selectedYear, onFestivalClick]);

  const closeSidebar = useCallback(() => {
    setIsSidebarOpen(false);
    setSelectedDate(null);
    setIsFestival(false);
    setSelectedFestivalName(null);
  }, []);

  return (
    <>
      <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#0F172A] to-[#1E293B] p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar size={18} className="text-blue-400" />
            <h3 className="text-sm font-semibold text-[#F1F5F9]">Festival Calendar</h3>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={goPrev}
              disabled={!canGoPrev}
              className="rounded-lg border border-white/10 bg-white/5 p-1.5 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronLeft size={14} className="text-[#94A3B8]" />
            </button>
            <span className="min-w-[120px] px-3 py-1 text-center text-xs font-medium text-[#CBD5E1]">
              {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
            </span>
            <button
              onClick={goNext}
              disabled={!canGoNext}
              className="rounded-lg border border-white/10 bg-white/5 p-1.5 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
            >
              <ChevronRight size={14} className="text-[#94A3B8]" />
            </button>
          </div>
        </div>

        <div
          ref={stripRef}
          className="flex gap-1.5 overflow-x-auto pb-2 scroll-smooth"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#334155 transparent' }}
        >
          {loading
            ? Array.from({ length: numDays }, (_, i) => (
                <div key={i} className="h-[62px] w-[52px] flex-shrink-0 animate-pulse rounded-lg bg-white/5" />
              ))
            : Array.from({ length: numDays }, (_, i) => {
                const day = i + 1;
                const festival = festivalMap[day] || null;
                const todayFlag = isToday(day, selectedMonth, selectedYear);
                const past = isPastDay(day, selectedMonth, selectedYear);
                const dayDate = new Date(selectedYear, selectedMonth - 1, day);
                const dayName = DAY_ABBR[dayDate.getDay()];

                let cellClass = 'border-white/5 bg-white/[0.03]';
                if (todayFlag) cellClass = 'border-blue-500 bg-blue-500/10';
                if (festival) cellClass = 'border-amber-400 bg-amber-400/[0.12]';

                return (
                  <button
                    key={day}
                    data-today={todayFlag ? 'true' : undefined}
                    onClick={() => openSidebarForDay(day, festival)}
                    className={`
                      relative flex h-[62px] w-[52px] flex-shrink-0 cursor-pointer flex-col items-center justify-center gap-0.5 rounded-lg border transition-all
                      ${cellClass}
                      ${past && !todayFlag ? 'opacity-40' : ''}
                      ${festival ? 'hover:bg-amber-400/20' : 'hover:bg-blue-500/10'}
                    `}
                  >
                    {festival && (() => {
                      const badge = festivalBadgeContent(festival);
                      if (badge.type === 'dot') {
                        return (
                          <span
                            aria-hidden="true"
                            className="absolute -top-0.5 h-1.5 w-1.5 rounded-full bg-amber-400"
                          />
                        );
                      }
                      return (
                        <span className="absolute -top-0.5 text-[10px] leading-none text-amber-300">
                          {badge.value}
                        </span>
                      );
                    })()}
                    <span className={`text-[9px] ${todayFlag ? 'text-blue-300' : 'text-[#64748B]'} ${festival ? 'mt-1.5' : ''}`}>
                      {dayName}
                    </span>
                    <span className={`text-sm leading-none ${todayFlag ? 'font-bold text-blue-300' : 'text-[#CBD5E1]'}`}>
                      {day}
                    </span>
                  </button>
                );
              })}
        </div>

        {error && <p className="mt-2 text-xs text-red-300">{error}</p>}

        {variant === 'full' && (
          <div className="mt-4 space-y-3">
            {!loading && festivals.length === 0 && (
              <div className="py-6 text-center">
                <p className="text-sm text-[#94A3B8]">
                  No festivals in {MONTH_NAMES[selectedMonth - 1]} {selectedYear}
                </p>
                {nextFestival && (
                  <>
                    <p className="mt-2 text-xs text-[#64748B]">
                      Next festival: <span className="text-amber-300">{nextFestival.festival_name}</span> on{' '}
                      {formatFullDate(nextFestival.date)} - {getDaysUntil(nextFestival.date)} days away
                    </p>
                    <button
                      onClick={() => jumpToFestival(nextFestival)}
                      className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-4 py-1.5 text-xs font-medium text-amber-300 transition hover:bg-amber-400/20"
                    >
                      Jump to {MONTH_NAMES[new Date(`${nextFestival.date}T00:00:00`).getMonth()]}
                    </button>
                  </>
                )}
              </div>
            )}

            {festivals.map((f) => {
              const du = getDaysUntil(f.date);
              const label = daysUntilLabel(du);
              const cats = f.categories || [];
              const multiplier = Number(f.demand_multiplier || 1);
              const minLead = Math.min(...(cats.length ? cats.map((c) => leadTimes[c] ?? 5) : [5]));
              const isHighlighted = highlightedFestival === f.festival_name;

              return (
                <div
                  key={`${f.festival_name}-${f.date}`}
                  ref={(el) => {
                    cardRefs.current[f.festival_name] = el;
                  }}
                  className={`
                    overflow-hidden rounded-xl border border-white/10 bg-white/[0.02] transition-all
                    ${urgencyBorder(du)}
                    ${isHighlighted ? 'ring-1 ring-amber-400/50' : ''}
                  `}
                >
                  <div className="flex items-center justify-between px-4 pb-2 pt-3">
                    <div className="flex items-center gap-2">
                      <span className="text-base">
                        {FESTIVAL_EMOJI[f.festival_name] || '🎉'}
                      </span>
                      <span className="text-sm font-semibold text-[#F1F5F9]">{f.festival_name}</span>
                    </div>
                    <span className={`text-xs ${label.cls}`}>{label.text}</span>
                  </div>
                  <p className="-mt-1 px-4 pb-2 text-xs text-[#64748B]">{formatFullDate(f.date)}</p>

                  <div className="space-y-2 border-t border-white/5 px-4 py-3">
                    <p className="mb-1 text-[10px] uppercase tracking-wider text-[#64748B]">Expected Demand Impact</p>
                    {cats.map((cat) => {
                      const catUplift = f.category_uplifts?.[cat];
                      const pct = Math.round(
                        catUplift != null ? catUplift * 100 : (multiplier - 1) * 100,
                      );
                      const barWidth = Math.min(100, pct * 2);
                      return (
                        <div key={cat} className="flex items-center gap-2">
                          <span className="w-3 text-xs">{CATEGORY_EMOJI[cat] || '📦'}</span>
                          <span className="w-20 truncate text-xs text-[#CBD5E1]">{cat}</span>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/5">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-300"
                              style={{ width: `${barWidth}%` }}
                            />
                          </div>
                          <span className="w-10 text-right text-xs font-medium text-amber-300">+{pct}%</span>
                        </div>
                      );
                    })}
                  </div>

                  {du >= 0 && (
                    <div className="border-t border-white/5 bg-white/[0.01] px-4 py-2.5">
                      <p className="text-xs text-amber-200">Stock up by {getStockUpDate(f.date, minLead)}</p>
                      <p className="mt-0.5 text-[10px] text-[#64748B]">
                        Order {minLead} days before festival accounting for your lead time
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {isSidebarOpen && (
        <PredictionSidebar
          isOpen={isSidebarOpen}
          selectedDate={selectedDate}
          isFestival={isFestival}
          selectedFestivalName={selectedFestivalName}
          stocks={['Snacks', 'Staples', 'Edible Oil']}
          onClose={closeSidebar}
        />
      )}
    </>
  );
}
