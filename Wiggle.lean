import Mathlib
import Lean

namespace Wiggle

def jsonEscape (s : String) : String :=
  let chars := (s.toList.map fun
    | '"' => ['\\', '"']
    | '\\' => ['\\', '\\']
    | '\n' => ['\\', 'n']
    | '\r' => ['\\', 'r']
    | '\t' => ['\\', 't']
    | c => [c]).flatten
  String.ofList chars

def jsonField (key value : String) : String :=
  "\"" ++ jsonEscape key ++ "\":\"" ++ jsonEscape value ++ "\""

def jsonNatField (key : String) (value : Nat) : String :=
  "\"" ++ jsonEscape key ++ "\":" ++ toString value

def jsonObject (fields : List String) : String :=
  "{" ++ String.intercalate "," fields ++ "}"

open Lean Elab Command Meta in
elab "#wiggle_dump_instances" : command => do
  let env ← getEnv
  env.constants.forM fun name info => do
    let isInst ← Command.liftCoreM <| Lean.Meta.isInstance name
    if isInst then
      let typeFmt ← liftTermElabM <| Meta.ppExpr info.type
      let priority? ← Command.liftCoreM <| Lean.Meta.getInstancePriority? name
      let attrKind? ← Command.liftCoreM <| Lean.Meta.getInstanceAttrKind? name
      let priority := match priority? with
        | some n => n
        | none => 1000
      let attrKind := match attrKind? with
        | some .global => "global"
        | some .scoped => "scoped"
        | some .local => "local"
        | none => "none"
      IO.println <| jsonObject [
        jsonField "name" (toString name),
        jsonField "type" typeFmt.pretty,
        jsonNatField "priority" priority,
        jsonField "attrKind" attrKind
      ]

end Wiggle

-- tactic to negate state, from Aristotle:
open Lean Meta Elab Tactic in
elab "revert_all" : tactic => do
  let goals ← getGoals
  let mut newGoals : List MVarId := []
  for mvarId in goals do
    newGoals := newGoals.append [(← mvarId.revertAll)]
  setGoals newGoals

open Lean.Elab.Tactic in
macro "negate_state" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_all
    apply (by admit : ∀ {p : Prop}, ¬p → p)
    try (push Not; guard_goal_nums 1)
  )
)

-- Reverts only Prop-typed hypotheses, leaving type variables in context.
-- This lets contrapose! see a plain implication instead of a dependent ∀.
open Lean Meta Elab Tactic in
elab "revert_props" : tactic => do
  let goal ← getMainGoal
  let decl ← goal.getDecl
  let propFVars ← decl.lctx.foldlM (init := #[]) fun acc d => do
    if d.isImplementationDetail then return acc
    if ← isProp d.type then return acc.push d.fvarId
    else return acc
  let (_, newGoal) ← goal.revert propFVars (preserveOrder := true)
  replaceMainGoal [newGoal]

-- Tactic for getting the contrapositive of an implication
open Lean.Elab.Tactic in
macro "contrapositive" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    contrapose
    simp only [not_and_or, not_le, not_lt]
    guard_goal_nums 1
  )
)

-- Tactic for getting the converse of an implication
open Lean.Elab.Tactic in
macro "converse" : tactic => `(tactic|
  (
    guard_goal_nums 1
    revert_props
    try (simp only [← and_imp])
    apply (by admit : ∀ {p q : Prop}, (q → p) → (p → q))
    guard_goal_nums 1
  )
)


-- Removes Prop-valued hypotheses that are not used by the target or by later
-- hypotheses. This implements generalization by weakening hypotheses.
open Lean Meta Elab Tactic in
elab "clear_unused_props" : tactic => do
  let mut goal ← getMainGoal
  let decl ← goal.getDecl
  let fvars := decl.lctx.foldl (init := #[]) fun acc d =>
    if d.isImplementationDetail then acc else acc.push d.fvarId
  for fvarId in fvars.reverse do
    try
      let localDecl ← fvarId.getDecl
      if ← isProp localDecl.type then
        goal ← goal.clear fvarId
    catch _ =>
      pure ()
  replaceMainGoal [goal]

open Lean.Elab.Tactic in
macro "generalize_statement_by_weakening_hypotheses" : tactic => `(tactic|
  (
    guard_goal_nums 1
    clear_unused_props
    guard_goal_nums 1
  )
)

open Lean.Elab.Tactic in
macro "generalize_state" : tactic => `(tactic|
  (
    generalize_statement_by_weakening_hypotheses
  )
)

open Lean Meta Elab Tactic Term in
def replaceMainGoalWithForExtraction (newTarget : Expr) : TacticM Unit := do
  let goal ← getMainGoal
  let oldTarget ← instantiateMVars (← goal.getType)
  let newGoal ← mkFreshExprMVarAt (← getLCtx) (← getLocalInstances)
    newTarget MetavarKind.syntheticOpaque (← goal.getTag)
  let bridgeType ← mkArrow newTarget oldTarget
  goal.assign (mkApp (← mkSorry bridgeType true) newGoal)
  replaceMainGoal [newGoal.mvarId!]

-- Adds a new Prop-valued assumption to the statement. The hypothesis is supplied
-- explicitly, because Lean cannot infer which stronger context you want.
open Lean Meta Elab Tactic Term in
elab "weaken_statement_by_strengthening_hypotheses " hyp:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `weaken_statement_by_strengthening_hypotheses
    pure goal
  withMainContext do
    let oldTarget ← instantiateMVars (← getMainTarget)
    let hypType ← Term.elabType hyp
    replaceMainGoalWithForExtraction (← mkArrow hypType oldTarget)

-- Replaces the current conclusion with an explicitly supplied stronger target.
-- The caller is responsible for choosing a proposition that implies the original.
open Lean Meta Elab Tactic Term in
elab "strengthen_statement_by_strengthening_conclusion " newGoal:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `strengthen_statement_by_strengthening_conclusion
    pure goal
  withMainContext do
    let newTarget ← Term.elabType newGoal
    replaceMainGoalWithForExtraction newTarget

-- Replaces the current conclusion with an explicitly supplied weaker target.
-- This is a statement-generation tactic: the admitted bridge lets extract_goal
-- print the requested perturbation while Python/Lean later checks compilation.
open Lean Meta Elab Tactic Term in
elab "weaken_statement_by_weakening_conclusion " newGoal:term : tactic => do
  liftMetaTactic1 fun goal => do
    goal.checkNotAssigned `weaken_statement_by_weakening_conclusion
    pure goal
  withMainContext do
    let newTarget ← Term.elabType newGoal
    replaceMainGoalWithForExtraction newTarget


-- `mutate_goal_type`: replaces `⊢ T` with `⊢ ∀ (h_extra : True), T`.
open Lean Meta Elab Tactic in
elab "mutate_goal_type" : tactic => do
  let g ← getMainGoal
  let decl ← g.getDecl
  let oldTy := decl.type
  -- Build: ∀ (h_extra : True), oldTy
  let newTy := mkForall `h_extra BinderInfo.default (mkConst ``True) oldTy
  -- Create a new metavariable with the mutated type
  let newGoal ← mkFreshExprMVar newTy
  replaceMainGoal [newGoal.mvarId!]


open Lean.Elab.Tactic in
macro "specialize_state" : tactic =>
  `(tactic|
    ( mutate_goal_type
      extract_goal
    )
  )
