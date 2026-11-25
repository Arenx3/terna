import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type UniqueIdentifier,
} from "@dnd-kit/core"
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVerticalIcon } from "lucide-react"
import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"

type Keyed = { key: string }

/**
 * A vertical list reordered by dragging a handle, with the mouse or the
 * keyboard (Space to pick up, arrows to move, Space to drop). Every move is
 * announced to screen readers in the reader's language.
 */
export function SortableList<T extends Keyed>({
  items,
  onReorder,
  describe,
  renderItem,
  disabled = false,
  className,
}: {
  items: T[]
  onReorder: (items: T[]) => void
  /** How a screen reader names an item, e.g. "Requirement 2: Kubernetes". */
  describe: (item: T, index: number) => string
  renderItem: (item: T, index: number, handle: ReactNode) => ReactNode
  disabled?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const indexOf = (id: UniqueIdentifier) =>
    items.findIndex((item) => item.key === id)
  const name = (id: UniqueIdentifier) => {
    const index = indexOf(id)
    return index < 0 ? "" : describe(items[index], index)
  }
  const total = items.length
  const announcements: Announcements = {
    onDragStart: ({ active }) =>
      t("sortable.picked", {
        item: name(active.id),
        position: indexOf(active.id) + 1,
        total,
      }),
    onDragOver: ({ active, over }) =>
      over
        ? t("sortable.moved", {
            item: name(active.id),
            position: indexOf(over.id) + 1,
            total,
          })
        : undefined,
    onDragEnd: ({ active, over }) =>
      t("sortable.dropped", {
        item: name(active.id),
        position: indexOf((over ?? active).id) + 1,
        total,
      }),
    onDragCancel: ({ active }) =>
      t("sortable.cancelled", {
        item: name(active.id),
        position: indexOf(active.id) + 1,
      }),
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return
    onReorder(arrayMove(items, indexOf(active.id), indexOf(over.id)))
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={onDragEnd}
      accessibility={{
        announcements,
        screenReaderInstructions: { draggable: t("sortable.instructions") },
      }}
    >
      <SortableContext
        items={items.map((item) => item.key)}
        strategy={verticalListSortingStrategy}
        disabled={disabled}
      >
        <ol className={className}>
          {items.map((item, index) => (
            <SortableRow
              key={item.key}
              id={item.key}
              label={describe(item, index)}
              disabled={disabled}
            >
              {(handle) => renderItem(item, index, handle)}
            </SortableRow>
          ))}
        </ol>
      </SortableContext>
    </DndContext>
  )
}

function SortableRow({
  id,
  label,
  disabled,
  children,
}: {
  id: string
  label: string
  disabled: boolean
  children: (handle: ReactNode) => ReactNode
}) {
  const { t } = useTranslation()
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled })

  const handle = (
    <button
      type="button"
      ref={setActivatorNodeRef}
      {...attributes}
      {...listeners}
      aria-label={t("sortable.handle", { item: label })}
      disabled={disabled}
      className="grid size-8 shrink-0 cursor-grab touch-none place-items-center rounded-md text-faint-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none active:cursor-grabbing disabled:pointer-events-none disabled:opacity-40"
    >
      <GripVerticalIcon aria-hidden="true" className="size-4" />
    </button>
  )

  return (
    <li
      ref={setNodeRef}
      style={{
        transform: CSS.Translate.toString(transform),
        transition,
      }}
      className={cn(
        "relative",
        isDragging && "z-10 rounded-lg bg-popover ring-1 ring-border"
      )}
    >
      {children(handle)}
    </li>
  )
}
