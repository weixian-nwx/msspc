"""Build the populated attendance deck from the template + mappings + state.

For each grade and role (present / absent) the relevant participants are cloned
from that section's template slide, filled with name + title, and inserted
immediately after that section's title slide, in original input-excel order.
The template source slides are removed from the final deck.
"""
from __future__ import annotations

from pptx import Presentation

from app import config
from app.db import Database
from app.pptx_utils import (
    delete_slide,
    duplicate_slide,
    find_shape_by_id,
    move_slide_to,
    set_shape_text,
    set_slide_notes,
    slide_index_of,
)


class BuildError(Exception):
    pass


def build_deck(db: Database, out_path: str) -> str:
    """Populate the template deck and save to ``out_path``. Returns the path."""
    template = db.get_meta("template_pptx")
    if not template:
        raise BuildError("No template deck has been imported.")
    if not db.mappings_complete():
        raise BuildError("Slide mappings are incomplete. Configure mappings for every grade.")

    prs = Presentation(template)
    orig_slides = list(prs.slides)
    n = len(orig_slides)

    def slide_at(idx: int):
        if idx < 0 or idx >= n:
            raise BuildError(f"Mapped slide index {idx} is out of range for this deck.")
        return orig_slides[idx]

    participants = db.all_participants()  # already ordered by row_index

    # Capture template-slide elements to delete after cloning (dedup by element id).
    template_elements = []

    for grade in db.distinct_grades():
        for role in config.ROLES:
            title_map = db.get_mapping(grade, role, config.KIND_TITLE)
            tmpl_map = db.get_mapping(grade, role, config.KIND_TEMPLATE)
            if not title_map or not tmpl_map:
                raise BuildError(f"Missing mapping for grade '{grade}', {role}.")

            title_slide = slide_at(title_map["slide_idx"])
            tmpl_slide = slide_at(tmpl_map["slide_idx"])
            name_shape_id = tmpl_map["name_shape_id"]
            title_shape_id = tmpl_map["title_shape_id"]
            bu_shape_id = tmpl_map["bu_shape_id"]

            if all(tmpl_slide._element is not e for e in template_elements):
                template_elements.append(tmpl_slide._element)

            # People in this grade matching this role, in input order.
            want_present = role == config.ROLE_PRESENT
            people = [p for p in participants if p.grade == grade and p.present == want_present]

            # Insert clones consecutively right after the title slide.
            insert_pos = slide_index_of(prs, title_slide._element) + 1
            for person in people:
                clone = duplicate_slide(prs, tmpl_slide)

                name_shape = find_shape_by_id(clone, name_shape_id)
                title_shape = find_shape_by_id(clone, title_shape_id)
                bu_shape = find_shape_by_id(clone, bu_shape_id) if bu_shape_id else None
                if name_shape is not None:
                    set_shape_text(name_shape, person.name)
                if title_shape is not None:
                    set_shape_text(title_shape, person.title)
                if bu_shape is not None:
                    set_shape_text(bu_shape, person.bu)
                if person.seat_no:
                    set_slide_notes(clone, person.seat_no)

                move_slide_to(prs, clone, insert_pos)
                insert_pos += 1

    # Remove the template source slides from the final deck.
    for el in template_elements:
        delete_slide(prs, el)

    prs.save(out_path)
    return out_path
