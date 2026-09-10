// Behavioral AD7476A (Rev. G) serial model for simulation only.
// CS falling: latch analog_code, first leading zero on SDATA.
// Later bits on SCLK falling: 3 more zeros, then DB11..DB0.
module adc_ad7476a_model (
    input  logic        cs_n,
    input  logic        sclk,
    output logic        sdata,
    input  logic [11:0] analog_code
);

    logic [15:0] shreg;

    // First leading zero on CS fall; remaining bits on SCLK fall.
    always @(negedge cs_n or negedge sclk) begin
        if (sclk) begin
            shreg <= {4'b0000, analog_code};
        end else if (!cs_n) begin
            shreg <= {shreg[14:0], 1'b0};
        end
    end

    // Idle is 0. The real part three-states SDATA while CS is high;
    // Icarus X-propagates 1'bz, so the model stays driven.
    assign sdata = cs_n ? 1'b0 : shreg[15];

endmodule
