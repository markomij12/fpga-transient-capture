// Test wrapper: synthesizable capture_top + sim-only AD7476A model.
// Same pattern as adc_spi_tb. Small defaults for Icarus; hardware
// defaults stay on capture_top.
module capture_top_tb #(
    parameter int DEPTH              = 32,
    parameter int WIDTH              = 12,
    parameter int PRE_TRIGGER        = 8,
    parameter int HYSTERESIS         = 4,
    parameter int CLKS_PER_BIT       = 8,
    parameter int CLKS_PER_SCLK      = 2,
    parameter int SAMPLE_PERIOD_CLKS = 40
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        uart_rx,
    output logic        uart_tx,
    input  logic [11:0] analog_code,
    input  logic        arm_btn,
    output logic [1:0]  status,
    output logic        adc_cs_n,
    output logic        adc_sclk
);

    logic adc_sdata;

    capture_top #(
        .DEPTH             (DEPTH),
        .WIDTH             (WIDTH),
        .PRE_TRIGGER       (PRE_TRIGGER),
        .HYSTERESIS        (HYSTERESIS),
        .CLKS_PER_BIT      (CLKS_PER_BIT),
        .CLKS_PER_SCLK     (CLKS_PER_SCLK),
        .SAMPLE_PERIOD_CLKS(SAMPLE_PERIOD_CLKS)
    ) dut (
        .clk      (clk),
        .rst      (rst),
        .uart_rx  (uart_rx),
        .uart_tx  (uart_tx),
        .adc_cs_n (adc_cs_n),
        .adc_sclk (adc_sclk),
        .adc_sdata(adc_sdata),
        .arm_btn  (arm_btn),
        .status   (status)
    );

    adc_ad7476a_model model (
        .cs_n       (adc_cs_n),
        .sclk       (adc_sclk),
        .sdata      (adc_sdata),
        .analog_code(analog_code)
    );

endmodule
