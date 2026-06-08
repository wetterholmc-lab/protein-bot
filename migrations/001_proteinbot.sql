CREATE TABLE IF NOT EXISTS proteinbot_users (
    telegram_id          bigint PRIMARY KEY,
    age                  int NOT NULL,
    weight_kg            float NOT NULL,
    height_cm            float NOT NULL,
    sex                  text NOT NULL,
    activity_level       text NOT NULL,
    goal                 text NOT NULL,
    diet_style           text NOT NULL,
    pregnant_or_breastfeeding bool,
    protein_goal_g       int NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS proteinbot_meals (
    id                   serial PRIMARY KEY,
    telegram_id          bigint NOT NULL REFERENCES proteinbot_users(telegram_id),
    logged_at            timestamptz NOT NULL DEFAULT now(),
    description          text NOT NULL,
    protein_min_g        int NOT NULL,
    protein_max_g        int NOT NULL,
    protein_actual_g     int,
    recipe_id            int
);

CREATE TABLE IF NOT EXISTS proteinbot_recipes (
    id                        serial PRIMARY KEY,
    telegram_id               bigint NOT NULL REFERENCES proteinbot_users(telegram_id),
    name                      text NOT NULL,
    ingredients               jsonb NOT NULL,
    portions                  int NOT NULL,
    protein_per_portion_min_g int NOT NULL,
    protein_per_portion_max_g int NOT NULL,
    created_at                timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE proteinbot_meals
    ADD CONSTRAINT fk_recipe
    FOREIGN KEY (recipe_id) REFERENCES proteinbot_recipes(id)
    DEFERRABLE INITIALLY DEFERRED;
