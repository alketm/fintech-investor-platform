# Intent

Source of truth for what we build and why. One folder per feature:

```
intent/
  <feature-slug>/
    intent.md   # accepted by the product owner
    spec.md     # written from the accepted intent
    plan.md     # from plan mode; updated in the same commit when implementation departs from it
```

Start a feature by copying `_templates/`. Each file is committed when its stage is accepted;
the next stage starts from that commit.
