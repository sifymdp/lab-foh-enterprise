import { useCallback, useEffect, useMemo, useState } from 'react'
import { menuApi, type MenuItem } from '../api/extensions'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { humanizeApiError } from '../lib/apiErrors'

export interface CuisineCategory {
  id: string
  label: string
  icon: string
  desc: string
  themeColor: string
}

export const HOTEL_CUISINES: CuisineCategory[] = [
  { id: 'South Indian', label: 'South Indian', icon: '🌶️', desc: 'Dosa, Chettinad, Malabar & Coastal Heritage', themeColor: '#ea580c' },
  { id: 'North Indian', label: 'North Indian', icon: '🍛', desc: 'Royal Mughlai, Awadhi Dum Biryani & Tandoor', themeColor: '#d97706' },
  { id: 'Chinese & Pan-Asian', label: 'Chinese & Pan-Asian', icon: '🥢', desc: 'Dim Sum, Sichuan Wok & Hand-Pulled Noodles', themeColor: '#dc2626' },
  { id: 'Italian & Continental', label: 'Italian & Continental', icon: '🍝', desc: 'Handcrafted Pasta, Risotto, Wood-Fired & Steaks', themeColor: '#059669' },
  { id: 'Liquor & Cocktails', label: 'Liquor & Cocktails', icon: '🍸', desc: 'Single Malts, Reserve Wines & Smoked Cocktails', themeColor: '#7c3aed' },
  { id: 'Starters', label: 'Gourmet Starters', icon: '🥗', desc: 'Kebabs, Small Plates & Artisanal Appetizers', themeColor: '#0284c7' },
  { id: 'Desserts', label: 'Grand Desserts', icon: '✨', desc: '24K Gold Sweets, Warm Fondant & Haute Patisserie', themeColor: '#db2777' },
  { id: 'Drinks', label: 'Beverages', icon: '☕', desc: 'Artisanal Teas, Mocktails & Filter Coffee', themeColor: '#475569' },
]

export const MASTER_5STAR_MENU: Array<Omit<MenuItem, 'id'>> = [
  // ── South Indian Heritage ──
  { name: 'Ghee Roast Masala Dosa', description: 'Crisp golden crepe roasted in A2 desi ghee with spiced potato masala & artisanal trio of coconut chutneys', price: 280, category: 'South Indian', available: true, displayOrder: 1 },
  { name: 'Chettinad Spiced Chicken Sukka', description: 'Tender chicken morsels tossed in stone-ground 18-spice Chettinad masala with curry leaf crisp', price: 480, category: 'South Indian', available: true, displayOrder: 2 },
  { name: 'Malabar Parotta & Mutton Curry', description: 'Flaky layered Kerala parottas paired with slow-simmered coconut, fennel & black pepper mutton gravy', price: 580, category: 'South Indian', available: true, displayOrder: 3 },
  { name: 'Mysore Podi Mini Idlis & Vada', description: 'Steamed button idlis & crisp medu vada tossed in spiced gun-powder podi and organic clarified butter', price: 240, category: 'South Indian', available: true, displayOrder: 4 },
  { name: 'Banana Leaf Meen Pollichathu', description: 'Fresh sea bass fillet marinated in shallot-kokum paste, wrapped in banana leaf and slow pan-charred', price: 650, category: 'South Indian', available: true, displayOrder: 5 },

  // ── Royal North Indian ──
  { name: 'Murgh Makhani (Butter Chicken)', description: 'Tandoor-smoked chicken tikka in a velvety San Marzano tomato, cashew butter and kasuri methi gravy', price: 540, category: 'North Indian', available: true, displayOrder: 1 },
  { name: 'Dal Bukhara / 24-Hr Dal Makhani', description: 'Slow-simmered black urad lentils churned with churned white butter on overnight slow charcoal embers', price: 420, category: 'North Indian', available: true, displayOrder: 2 },
  { name: 'Awadhi Gosht Dum Biryani', description: 'Fragrant long-grain aged basmati rice layered with tender mutton shank, saffron, rose water in sealed handi', price: 680, category: 'North Indian', available: true, displayOrder: 3 },
  { name: 'Paneer Lababdar & Truffle Naan', description: 'Char-grilled cottage cheese cubes in rich onion-tomato gravy with hand-crushed whole spices & truffle naan', price: 460, category: 'North Indian', available: true, displayOrder: 4 },
  { name: 'Royal Galouti Kebab with Sheermal', description: 'Melt-in-mouth smoked lamb patties on saffron-scented mini sheermal breads with fresh mint relish', price: 520, category: 'North Indian', available: true, displayOrder: 5 },

  // ── Pan-Asian & Chinese ──
  { name: 'Truffle Edamame Dim Sum (4pcs)', description: 'Translucent steamed dumplings filled with water chestnut, shiitake mushroom & aromatic truffle oil drizzle', price: 480, category: 'Chinese & Pan-Asian', available: true, displayOrder: 1 },
  { name: 'Kung Pao Tiger Prawns', description: 'Wok-tossed jumbo tiger prawns with Sichuan peppers, crunchy roasted cashews, scallions & dried chillies', price: 640, category: 'Chinese & Pan-Asian', available: true, displayOrder: 2 },
  { name: 'Hakka Chilli Garlic Noodles', description: 'Hand-pulled artisan wheat noodles tossed with burnt garlic, bird\'s eye chilli and garden crisp bok choy', price: 380, category: 'Chinese & Pan-Asian', available: true, displayOrder: 3 },
  { name: 'Crispy Lotus Stem Honey Chilli', description: 'Wok-glazed golden lotus root crisps with kaffir lime zest, toasted sesame and wildflower honey', price: 390, category: 'Chinese & Pan-Asian', available: true, displayOrder: 4 },
  { name: 'Cantonese Steamed Sea Bass', description: 'Fresh line-caught fillet with julienned ginger, scallions, superior light soy and fragrant sesame oil', price: 720, category: 'Chinese & Pan-Asian', available: true, displayOrder: 5 },

  // ── Italian & Continental ──
  { name: 'Wild Forest Mushroom Risotto', description: 'Carnaroli rice cooked with porcini broth, shaved black winter truffle, aged Parmigiano-Reggiano and thyme', price: 580, category: 'Italian & Continental', available: true, displayOrder: 1 },
  { name: 'Wood-Fired Burrata Margherita', description: '48-hour fermented sourdough crust, San Marzano D.O.P. sauce, artisanal fresh burrata & sweet basil', price: 540, category: 'Italian & Continental', available: true, displayOrder: 2 },
  { name: 'Fettuccine Truffle Alfredo', description: 'Handcrafted egg pasta in rich cultured butter, heavy cream and freshly grated winter black truffle', price: 490, category: 'Italian & Continental', available: true, displayOrder: 3 },
  { name: 'Grilled New Zealand Lamb Chops', description: 'Herb-crusted lamb chops with rosemary jus, garlic confit potato mash and charred tenderstem asparagus', price: 950, category: 'Italian & Continental', available: true, displayOrder: 4 },

  // ── The Reserve Bar & Liquors ──
  { name: 'Smoked Rosemary Old Fashioned', description: 'Bourbon whiskey, Angostura aromatic bitters, raw demerara syrup infused with torched organic rosemary smoke', price: 650, category: 'Liquor & Cocktails', available: true, displayOrder: 1 },
  { name: 'Macallan 12 Single Malt (30ml)', description: 'Highland single malt scotch whisky with notes of rich dried fruits, vanilla, oak and wood spice', price: 850, category: 'Liquor & Cocktails', available: true, displayOrder: 2 },
  { name: 'Royal Saffron Gin & Tonic', description: 'Artisanal dry gin infused with Kashmiri saffron, Mediterranean tonic water and dehydrated citrus wheel', price: 580, category: 'Liquor & Cocktails', available: true, displayOrder: 3 },
  { name: 'Chianti Classico Riserva (Glass)', description: 'Elegant Tuscan red wine with bouquet of violet, ripe cherry, French oak spice and velvety tannins', price: 750, category: 'Liquor & Cocktails', available: true, displayOrder: 4 },
  { name: 'Belgian Hoegaarden / Craft Beer', description: 'Chilled premium craft wheat beer with coriander and orange peel notes, served in signature chalice', price: 380, category: 'Liquor & Cocktails', available: true, displayOrder: 5 },

  // ── Grand Desserts ──
  { name: '24K Gold Leaf Shahi Tukda', description: 'Crisp saffron brioche soaked in cardamom syrup, layered with thick rabri, pistachio dust & edible gold leaf', price: 320, category: 'Desserts', available: true, displayOrder: 1 },
  { name: 'Valrhona Warm Chocolate Fondant', description: 'Molten dark chocolate center served with handcrafted Madagascar vanilla bean gelato and berry coulis', price: 360, category: 'Desserts', available: true, displayOrder: 2 },
  { name: 'Classic Espresso Tiramisu', description: 'Savoiardi ladyfingers soaked in Illy espresso, layered with whipped mascarpone and Valrhona cocoa dust', price: 340, category: 'Desserts', available: true, displayOrder: 3 },
]

interface FormState {
  name: string
  description: string
  price: string
  category: string
  available: boolean
  displayOrder: string
}

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  price: '',
  category: 'South Indian',
  available: true,
  displayOrder: '1',
}

function getDietaryType(item: MenuItem): 'veg' | 'non-veg' | 'liquor' {
  if (item.category === 'Liquor & Cocktails') return 'liquor'
  const text = `${item.name} ${item.description || ''}`.toLowerCase()
  const nonVegKeywords = ['chicken', 'mutton', 'prawn', 'prawns', 'fish', 'sea bass', 'lamb', 'steak', 'meat', 'calamari', 'duck', 'egg']
  if (nonVegKeywords.some((k) => text.includes(k))) return 'non-veg'
  return 'veg'
}

export function MenuPage() {
  const [items, setItems] = useState<MenuItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [populating, setPopulating] = useState(false)

  // Filters & View State
  const [activeCuisine, setActiveCuisine] = useState<string>('All')
  const [searchQuery, setSearchQuery] = useState('')
  const [dietaryFilter, setDietaryFilter] = useState<'ALL' | 'VEG' | 'NON_VEG' | 'LIQUOR'>('ALL')
  const [sortBy, setSortBy] = useState<'ORDER' | 'PRICE_ASC' | 'PRICE_DESC' | 'NAME'>('ORDER')
  const [viewMode, setViewMode] = useState<'GRID' | 'TABLE'>('GRID')

  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'info' | 'error' } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  const showToast = (msg: string, type: 'success' | 'info' | 'error' = 'success') => {
    setToast({ msg, type })
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await menuApi.list()
      setItems(data)
    } catch (e) {
      setError(humanizeApiError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3500)
    return () => clearTimeout(t)
  }, [toast])

  const openAdd = (defaultCategory?: string) => {
    setEditingId(null)
    setForm({
      ...EMPTY_FORM,
      category: defaultCategory && defaultCategory !== 'All' ? defaultCategory : 'South Indian',
      displayOrder: String(items.length + 1),
    })
    setShowForm(true)
  }

  const openEdit = (item: MenuItem) => {
    setEditingId(item.id)
    setForm({
      name: item.name,
      description: item.description ?? '',
      price: String(item.price),
      category: item.category,
      available: item.available,
      displayOrder: String(item.displayOrder),
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.name.trim() || !form.price) return
    setSaving(true)
    setError('')
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        price: parseFloat(form.price),
        category: form.category,
        available: form.available,
        displayOrder: parseInt(form.displayOrder) || 0,
      }
      if (editingId) {
        await menuApi.update(editingId, payload)
        showToast(`Updated "${form.name}"`)
      } else {
        await menuApi.create(payload)
        showToast(`Added "${form.name}" to ${form.category}`)
      }
      setShowForm(false)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await menuApi.remove(id)
      setItems((prev) => prev.filter((i) => i.id !== id))
      setDeleteTarget(null)
      showToast('Item removed from menu', 'info')
    } catch (e) {
      setError(humanizeApiError(e))
    }
  }

  const handleToggle = async (item: MenuItem) => {
    try {
      const updated = await menuApi.toggle(item.id, !item.available)
      setItems((prev) => prev.map((i) => (i.id === item.id ? updated : i)))
      showToast(`${item.name} is now ${updated.available ? 'Live (Available)' : '86\'d (Sold Out)'}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Toggle failed')
    }
  }

  // Populate Master 5-Star Menu
  const handlePopulate5StarMenu = async () => {
    if (!confirm('This will add the complete 5-Star Hotel Multi-Cuisine Catalog (South Indian, North Indian, Pan-Asian, Italian, Liquor & Desserts) to your active menu. Continue?')) {
      return
    }
    setPopulating(true)
    try {
      const existingNames = new Set(items.map((i) => i.name.toLowerCase().trim()))
      let addedCount = 0
      for (const dish of MASTER_5STAR_MENU) {
        if (!existingNames.has(dish.name.toLowerCase().trim())) {
          await menuApi.create(dish)
          addedCount++
        }
      }
      await load()
      showToast(`Successfully added ${addedCount} 5-Star luxury items to your menu!`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to seed 5-star menu')
    } finally {
      setPopulating(false)
    }
  }

  // Filtered & Sorted items
  const filteredItems = useMemo(() => {
    let result = [...items]

    // 1. Cuisine Filter
    if (activeCuisine !== 'All') {
      result = result.filter((i) => i.category.toLowerCase() === activeCuisine.toLowerCase())
    }

    // 2. Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      result = result.filter((i) =>
        i.name.toLowerCase().includes(q) ||
        (i.description && i.description.toLowerCase().includes(q)) ||
        i.category.toLowerCase().includes(q)
      )
    }

    // 3. Dietary Filter
    if (dietaryFilter !== 'ALL') {
      result = result.filter((i) => {
        const d = getDietaryType(i)
        if (dietaryFilter === 'VEG') return d === 'veg'
        if (dietaryFilter === 'NON_VEG') return d === 'non-veg'
        if (dietaryFilter === 'LIQUOR') return d === 'liquor'
        return true
      })
    }

    // 4. Sort
    result.sort((a, b) => {
      if (sortBy === 'PRICE_ASC') return a.price - b.price
      if (sortBy === 'PRICE_DESC') return b.price - a.price
      if (sortBy === 'NAME') return a.name.localeCompare(b.name)
      return (a.displayOrder || 0) - (b.displayOrder || 0)
    })

    return result
  }, [items, activeCuisine, searchQuery, dietaryFilter, sortBy])

  // Group items by category
  const allCategoryKeys = useMemo(() => {
    const defined = HOTEL_CUISINES.map((c) => c.id)
    const customInItems = Array.from(new Set(items.map((i) => i.category))).filter((c) => !defined.includes(c))
    return [...defined, ...customInItems]
  }, [items])

  const groupedByCuisine = useMemo(() => {
    const map: Record<string, MenuItem[]> = {}
    allCategoryKeys.forEach((k) => {
      const catItems = filteredItems.filter((i) => i.category.toLowerCase() === k.toLowerCase())
      if (catItems.length > 0) {
        map[k] = catItems
      }
    })
    return map
  }, [filteredItems, allCategoryKeys])

  if (loading) {
    return (
      <div className="page-loading" style={{ minHeight: '60vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div className="spinner" style={{ marginBottom: '1rem' }} />
        <p className="muted">Loading menu...</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1280px', margin: '0 auto' }}>
      {/* ── Toast Notification ── */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 1000,
          padding: '10px 18px',
          background: toast.type === 'error' ? '#dc2626' : toast.type === 'info' ? '#0f172a' : '#16a34a',
          color: '#fff',
          borderRadius: '8px',
          boxShadow: 'var(--shadow-md)',
          fontSize: '0.85rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          animation: 'fadeIn 0.2s ease',
        }}>
          <span>{toast.type === 'error' ? '✕' : toast.type === 'info' ? 'ℹ' : '✓'}</span>
          <span>{toast.msg}</span>
        </div>
      )}

      {/* ── Standard Page Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 700 }}>Menu</h2>
          <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.85rem' }}>
            Manage items, prices, and availability — updates table QR menus instantly
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handlePopulate5StarMenu}
            disabled={populating}
            style={{ fontSize: '0.8rem' }}
          >
            {populating ? 'Loading…' : 'Load Default Menu'}
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => openAdd(activeCuisine)}
            style={{ fontSize: '0.8rem' }}
          >
            + Add item
          </button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '12px 18px', marginBottom: 20, color: '#b91c1c', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.875rem' }}>
          <span>⚠️ {error}</span>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 700, color: '#b91c1c' }} onClick={() => setError('')}>✕</button>
        </div>
      )}

      {/* ── Cuisine Filter Tabs ── */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        marginBottom: '1.25rem',
        overflowX: 'auto',
        paddingBottom: '4px',
      }}>
        <button
          type="button"
          className={`cuisine-tab-btn ${activeCuisine === 'All' ? 'active' : ''}`}
          onClick={() => setActiveCuisine('All')}
        >
          <span>🌐</span>
          <span>All Cuisines</span>
          <span className="count-chip">{items.length}</span>
        </button>

        {HOTEL_CUISINES.map((cuisine) => {
          const count = items.filter((i) => i.category.toLowerCase() === cuisine.id.toLowerCase()).length
          const isActive = activeCuisine.toLowerCase() === cuisine.id.toLowerCase()

          return (
            <button
              key={cuisine.id}
              type="button"
              className={`cuisine-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveCuisine(cuisine.id)}
              title={cuisine.desc}
            >
              <span>{cuisine.icon}</span>
              <span>{cuisine.label}</span>
              <span className="count-chip">{count}</span>
            </button>
          )
        })}
      </div>

      {/* ── Search, Dietary Filter & View Controls Bar ── */}
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: '14px',
        padding: '1rem 1.25rem',
        marginBottom: '1.75rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        boxShadow: 'var(--shadow-sm)',
      }}>
        {/* Search Field */}
        <div style={{ position: 'relative', flex: '1 1 240px', minWidth: '220px' }}>
          <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            🔍
          </span>
          <input
            type="text"
            className="input"
            placeholder="Search dishes, ingredients, pairings..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ paddingLeft: '2.4rem', height: '40px', fontSize: '0.875rem' }}
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery('')}
              style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              ✕
            </button>
          )}
        </div>

        {/* Dietary Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setDietaryFilter('ALL')}
            style={{
              padding: '0.3rem 0.65rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: dietaryFilter === 'ALL' ? 'var(--text)' : 'var(--surface-2)',
              color: dietaryFilter === 'ALL' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
            }}
          >
            All Types
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setDietaryFilter('VEG')}
            style={{
              padding: '0.3rem 0.65rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: dietaryFilter === 'VEG' ? '#16a34a' : 'var(--surface-2)',
              color: dietaryFilter === 'VEG' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <span className="dietary-icon-box veg" style={{ width: 14, height: 14 }} />
            <span>Pure Veg</span>
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setDietaryFilter('NON_VEG')}
            style={{
              padding: '0.3rem 0.65rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: dietaryFilter === 'NON_VEG' ? '#dc2626' : 'var(--surface-2)',
              color: dietaryFilter === 'NON_VEG' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <span className="dietary-icon-box non-veg" style={{ width: 14, height: 14 }} />
            <span>Non-Veg</span>
          </button>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => setDietaryFilter('LIQUOR')}
            style={{
              padding: '0.3rem 0.65rem',
              fontSize: '0.78rem',
              fontWeight: 600,
              background: dietaryFilter === 'LIQUOR' ? '#7c3aed' : 'var(--surface-2)',
              color: dietaryFilter === 'LIQUOR' ? '#fff' : 'var(--text)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
            }}
          >
            🍸 The Bar
          </button>
        </div>

        {/* Sort & View Mode */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <select
            className="input"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            style={{ height: '38px', padding: '0 0.6rem', fontSize: '0.8rem', fontWeight: 600, minWidth: '130px' }}
          >
            <option value="ORDER">Default Order</option>
            <option value="PRICE_ASC">Price: Low to High</option>
            <option value="PRICE_DESC">Price: High to Low</option>
            <option value="NAME">Name: A to Z</option>
          </select>

          <div style={{ display: 'flex', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
            <button
              type="button"
              onClick={() => setViewMode('GRID')}
              style={{
                padding: '0.4rem 0.65rem',
                border: 'none',
                background: viewMode === 'GRID' ? 'var(--surface-2)' : 'var(--surface)',
                color: viewMode === 'GRID' ? 'var(--primary)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.9rem',
              }}
              title="Grid Card View"
            >
              ▦
            </button>
            <button
              type="button"
              onClick={() => setViewMode('TABLE')}
              style={{
                padding: '0.4rem 0.65rem',
                border: 'none',
                background: viewMode === 'TABLE' ? 'var(--surface-2)' : 'var(--surface)',
                color: viewMode === 'TABLE' ? 'var(--primary)' : 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.9rem',
                borderLeft: '1px solid var(--border)',
              }}
              title="Table / List View"
            >
              ☰
            </button>
          </div>
        </div>
      </div>

      {/* ── Menu Categories Sections ── */}
      {Object.entries(groupedByCuisine).map(([catKey, catItems]) => {
        const cuisineInfo = HOTEL_CUISINES.find((c) => c.id.toLowerCase() === catKey.toLowerCase()) ?? {
          id: catKey,
          label: catKey,
          icon: '🍽️',
          desc: 'Specialty culinary curation',
          themeColor: '#475569',
        }

        return (
          <div key={catKey} style={{ marginBottom: '2.5rem' }}>
            {/* Cuisine Section Header */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingBottom: '0.65rem',
              marginBottom: '1rem',
              borderBottom: '2px solid var(--border)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <span style={{ fontSize: '1.35rem' }}>{cuisineInfo.icon}</span>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800, color: 'var(--text)' }}>
                    {cuisineInfo.label}
                  </h3>
                  <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.78rem' }}>
                    {cuisineInfo.desc}
                  </p>
                </div>
                <span style={{
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  padding: '0.15rem 0.5rem',
                  borderRadius: '99px',
                  background: 'var(--surface-2)',
                  color: 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  marginLeft: '0.5rem',
                }}>
                  {catItems.length} {catItems.length === 1 ? 'item' : 'items'}
                </span>
              </div>

              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => openAdd(catKey)}
                style={{ fontSize: '0.8rem', color: cuisineInfo.themeColor, fontWeight: 700 }}
              >
                + Add {cuisineInfo.label}
              </button>
            </div>

            {/* View Mode 1: Luxury Cards Grid */}
            {viewMode === 'GRID' ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.15rem' }}>
                {catItems.map((item) => {
                  const dType = getDietaryType(item)

                  return (
                    <div key={item.id} className={`dish-card-luxury ${!item.available ? 'unavailable' : ''}`}>
                      {/* Card Header: Dietary Icon + Category Pill + Status */}
                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.65rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span className={`dietary-icon-box ${dType}`} title={dType === 'veg' ? 'Vegetarian' : dType === 'non-veg' ? 'Non-Vegetarian' : 'Alcoholic / Liquor'}>
                              {dType === 'liquor' ? '🍸' : ''}
                            </span>
                            <span style={{
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              color: cuisineInfo.themeColor,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}>
                              {item.category}
                            </span>
                          </div>

                          {!item.available && (
                            <span style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              padding: '0.15rem 0.45rem',
                              borderRadius: '4px',
                              background: '#fee2e2',
                              color: '#dc2626',
                              border: '1px solid #fca5a5',
                            }}>
                              86'd (Sold Out)
                            </span>
                          )}
                        </div>

                        {/* Dish Name */}
                        <h4 style={{ margin: '0 0 0.35rem', fontSize: '1rem', fontWeight: 700, color: 'var(--text)', lineHeight: 1.3 }}>
                          {item.name}
                        </h4>

                        {/* Dish Culinary Description */}
                        <p style={{
                          margin: 0,
                          fontSize: '0.8rem',
                          color: 'var(--text-muted)',
                          lineHeight: 1.45,
                          minHeight: '2.8em',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}>
                          {item.description || 'Artisan preparation crafted with premium culinary ingredients.'}
                        </p>
                      </div>

                      {/* Card Footer: Price & Actions */}
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        paddingTop: '0.75rem',
                        borderTop: '1px solid var(--border)',
                        marginTop: 'auto',
                      }}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Price</span>
                          <span style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text)', letterSpacing: '-0.02em' }}>
                            ₹{Number(item.price).toFixed(2)}
                          </span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <button
                            type="button"
                            onClick={() => handleToggle(item)}
                            style={{
                              padding: '0.35rem 0.65rem',
                              borderRadius: '6px',
                              border: '1px solid ' + (item.available ? '#bbf7d0' : '#e2e8f0'),
                              background: item.available ? '#f0fdf4' : 'var(--surface)',
                              color: item.available ? '#15803d' : 'var(--text-muted)',
                              fontSize: '0.75rem',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                            title="Toggle instant item availability (86/Live)"
                          >
                            {item.available ? '● Live' : '○ Off'}
                          </button>

                          <button
                            type="button"
                            onClick={() => openEdit(item)}
                            className="btn btn-ghost btn-sm"
                            style={{ padding: '0.35rem 0.5rem', fontSize: '0.8rem' }}
                            title="Edit dish details"
                          >
                            ✏️
                          </button>

                          <button
                            type="button"
                            onClick={() => setDeleteTarget(item.id)}
                            className="btn btn-ghost btn-sm"
                            style={{ padding: '0.35rem 0.5rem', fontSize: '0.8rem', color: 'var(--danger)' }}
                            title="Remove from menu"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              /* View Mode 2: Compact Table View */
              <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', boxShadow: 'var(--shadow-sm)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                  <thead>
                    <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                      <th style={{ padding: '10px 16px', width: '35px' }}>Type</th>
                      <th style={{ padding: '10px 16px' }}>Dish / Beverage</th>
                      <th style={{ padding: '10px 16px' }}>Category</th>
                      <th style={{ padding: '10px 16px', textAlign: 'right' }}>Price</th>
                      <th style={{ padding: '10px 16px', textAlign: 'center', width: '110px' }}>Status</th>
                      <th style={{ padding: '10px 16px', textAlign: 'right', width: '100px' }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {catItems.map((item, idx) => {
                      const dType = getDietaryType(item)
                      const isLast = idx === catItems.length - 1

                      return (
                        <tr key={item.id} style={{ borderBottom: isLast ? 'none' : '1px solid var(--border)', opacity: item.available ? 1 : 0.6 }}>
                          <td style={{ padding: '12px 16px' }}>
                            <span className={`dietary-icon-box ${dType}`} />
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <strong style={{ fontSize: '0.9rem', color: 'var(--text)' }}>{item.name}</strong>
                            {item.description && (
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>{item.description}</div>
                            )}
                          </td>
                          <td style={{ padding: '12px 16px', color: cuisineInfo.themeColor, fontWeight: 600 }}>
                            {item.category}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 800, fontSize: '0.95rem' }}>
                            ₹{Number(item.price).toFixed(2)}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                            <button
                              type="button"
                              onClick={() => handleToggle(item)}
                              style={{
                                padding: '3px 8px',
                                borderRadius: '99px',
                                border: '1px solid ' + (item.available ? '#bbf7d0' : '#fca5a5'),
                                background: item.available ? '#f0fdf4' : '#fef2f2',
                                color: item.available ? '#16a34a' : '#dc2626',
                                fontSize: '0.72rem',
                                fontWeight: 700,
                                cursor: 'pointer',
                              }}
                            >
                              {item.available ? '● Live' : '○ 86\'d'}
                            </button>
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '4px' }}>
                              <button type="button" onClick={() => openEdit(item)} className="btn btn-ghost btn-sm" style={{ padding: '3px 6px', fontSize: '0.75rem' }}>Edit</button>
                              <button type="button" onClick={() => setDeleteTarget(item.id)} className="btn btn-ghost btn-sm" style={{ padding: '3px 6px', fontSize: '0.75rem', color: 'var(--danger)' }}>Remove</button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}

      {/* Empty State */}
      {filteredItems.length === 0 && !loading && (
        <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '3rem 2rem', textAlign: 'center' }}>
          <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '0.75rem' }}>🍽️</span>
          <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.15rem' }}>No menu items found</h3>
          <p className="muted" style={{ margin: '0 0 1.25rem', fontSize: '0.85rem' }}>
            Try clearing search or filters, or add a new item.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setSearchQuery(''); setActiveCuisine('All'); setDietaryFilter('ALL'); }}>
              Reset Filters
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => openAdd(activeCuisine)}>
              + Add Item
            </button>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={!!deleteTarget}
        message="Remove this item from the menu?"
        confirmLabel="Remove"
        onConfirm={() => deleteTarget && handleDelete(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* ── Add / Edit Item Modal ── */}
      {showForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" style={{ background: 'rgba(15, 23, 42, 0.65)', backdropFilter: 'blur(4px)' }}>
          <div className="modal" style={{ maxWidth: '480px', borderRadius: '14px', padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>
                {editingId ? 'Edit Item' : 'Add Menu Item'}
              </h3>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.1rem', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Name *
                </label>
                <input
                  className="input"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Ghee Roast Dosa, Butter Chicken, Truffle Risotto..."
                  style={{ width: '100%', fontSize: '0.875rem' }}
                  autoFocus
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                    Category *
                  </label>
                  <select
                    className="input"
                    value={form.category}
                    onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                    style={{ width: '100%', fontSize: '0.85rem', padding: '0.5rem' }}
                  >
                    {HOTEL_CUISINES.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.icon} {c.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                    Price (₹) *
                  </label>
                  <div style={{ position: 'relative' }}>
                    <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', fontWeight: 700, color: 'var(--text-muted)' }}>₹</span>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.price}
                      onChange={(e) => setForm((f) => ({ ...f, price: e.target.value }))}
                      placeholder="0.00"
                      style={{ width: '100%', paddingLeft: '1.8rem', fontWeight: 700, fontSize: '0.9rem' }}
                    />
                  </div>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', fontWeight: 600, display: 'block', marginBottom: '0.35rem' }}>
                  Description
                </label>
                <textarea
                  className="input"
                  rows={3}
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="Ingredients, preparation notes, serving style..."
                  style={{ width: '100%', resize: 'vertical', fontSize: '0.85rem', padding: '0.6rem' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', alignItems: 'center', background: 'var(--surface-2)', padding: '0.75rem 1rem', borderRadius: '10px' }}>
                <div>
                  <label style={{ fontSize: '0.75rem', fontWeight: 600, display: 'block', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
                    Display Order
                  </label>
                  <input
                    className="input"
                    type="number"
                    min="1"
                    value={form.displayOrder}
                    onChange={(e) => setForm((f) => ({ ...f, displayOrder: e.target.value }))}
                    style={{ width: '80px', height: '34px', fontSize: '0.85rem', textAlign: 'center' }}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.5rem' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 }}>
                    <input
                      type="checkbox"
                      checked={form.available}
                      onChange={(e) => setForm((f) => ({ ...f, available: e.target.checked }))}
                      style={{ width: '18px', height: '18px' }}
                    />
                    <span>Available</span>
                  </label>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleSave}
                  disabled={saving || !form.name.trim() || !form.price}
                  style={{ fontWeight: 600, padding: '0 1.25rem' }}
                >
                  {saving ? 'Saving…' : editingId ? 'Save Changes' : 'Add Item'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
